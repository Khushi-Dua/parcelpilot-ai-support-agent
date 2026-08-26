import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parent
ZIP_PATH = ROOT / "AI Agent Assessment - Candidate Pack-20260826T134158Z-1-001.zip"
EXTRACT_DIR = ROOT / "data_pack"
PACK_DIR = EXTRACT_DIR / "AI Agent Assessment - Candidate Pack"
DATA_FILE = PACK_DIR / "ParcelPilot_Assessment_Data.xlsx"
REFERENCE_TIME = datetime(2026, 8, 16, 11, 0)

SOURCE_RANK = {
    "agreement": 5,
    "current_policy": 4,
    "product_guide": 4,
    "deprecated": 1,
    "historical": 1,
}


@dataclass
class ToolResult:
    name: str
    summary: str
    payload: Dict[str, Any]


class ParcelPilotData:
    def __init__(self) -> None:
        self._ensure_pack()
        self.accounts = pd.read_excel(DATA_FILE, sheet_name="accounts")
        self.orders = pd.read_excel(DATA_FILE, sheet_name="orders")
        self.tickets = pd.read_excel(DATA_FILE, sheet_name="tickets")
        self.accounts["account_name_lc"] = self.accounts["account_name"].str.lower()
        self.docs = self._load_docs()
        self.doc_account_scope = self._build_doc_account_scope(self.docs)
        self.doc_chunks, self.chunk_meta = self._chunk_docs(self.docs)
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.doc_matrix = self.vectorizer.fit_transform(self.doc_chunks)

    def _ensure_pack(self) -> None:
        if PACK_DIR.exists():
            return
        EXTRACT_DIR.mkdir(exist_ok=True)
        with zipfile.ZipFile(ZIP_PATH) as zf:
            zf.extractall(EXTRACT_DIR)

    def _load_docs(self) -> Dict[str, Dict[str, str]]:
        docs: Dict[str, Dict[str, str]] = {}
        for pdf in PACK_DIR.glob("*.pdf"):
            text = "\n".join((p.extract_text() or "") for p in PdfReader(str(pdf)).pages)
            lname = pdf.name.lower()
            doc_type = "current_policy"
            if "agreement" in lname:
                doc_type = "agreement"
            elif "deprecated" in lname:
                doc_type = "deprecated"
            elif "product_operations" in lname:
                doc_type = "product_guide"
            docs[pdf.name] = {"type": doc_type, "text": text}
        return docs

    def _build_doc_account_scope(self, docs: Dict[str, Dict[str, str]]) -> Dict[str, Optional[str]]:
        scoped_docs: Dict[str, Optional[str]] = {}
        for source, meta in docs.items():
            if meta["type"] != "agreement":
                scoped_docs[source] = None
                continue
            source_tokens = {t for t in re.split(r"[^a-z0-9]+", source.lower()) if t}
            best_match: Optional[str] = None
            best_score = 0
            for _, row in self.accounts.iterrows():
                account_tokens = {
                    t for t in re.split(r"[^a-z0-9]+", str(row["account_name"]).lower()) if len(t) >= 4
                }
                score = len(source_tokens & account_tokens)
                if score > best_score:
                    best_match = str(row["account_id"])
                    best_score = score
            scoped_docs[source] = best_match if best_score > 0 else None
        return scoped_docs

    def _chunk_docs(self, docs: Dict[str, Dict[str, str]]) -> Tuple[List[str], List[Dict[str, str]]]:
        chunks: List[str] = []
        meta: List[Dict[str, str]] = []
        for name, data in docs.items():
            paras = [p.strip() for p in re.split(r"\n\s*\n", data["text"]) if p.strip()]
            for para in paras:
                chunks.append(para)
                meta.append({"source": name, "type": data["type"]})
        return chunks, meta


def account_context(data: ParcelPilotData, mode: str, account_id: str, user_role: str) -> Dict[str, str]:
    if mode == "customer":
        return {"mode": mode, "account_id": account_id, "role": "customer"}
    return {"mode": mode, "account_id": account_id, "role": user_role}


def retrieve_documents(data: ParcelPilotData, query: str, ctx: Dict[str, str], k: int = 3) -> ToolResult:
    q = data.vectorizer.transform([query])
    sims = cosine_similarity(q, data.doc_matrix).flatten()
    allowed_idx: List[int] = []
    for i, meta in enumerate(data.chunk_meta):
        if ctx["mode"] != "customer" or meta["type"] != "agreement":
            allowed_idx.append(i)
            continue
        if data.doc_account_scope.get(meta["source"]) == ctx["account_id"]:
            allowed_idx.append(i)
    ranked = sorted(allowed_idx, key=lambda i: sims[i], reverse=True)[:k]
    docs = []
    for i in ranked:
        docs.append(
            {
                "source": data.chunk_meta[i]["source"],
                "type": data.chunk_meta[i]["type"],
                "score": float(sims[i]),
                "excerpt": data.doc_chunks[i][:350],
            }
        )
    return ToolResult("document_search", f"Retrieved {len(docs)} relevant policy/contract excerpts", {"matches": docs})


def _get_account(data: ParcelPilotData, account_id: str) -> Dict[str, Any]:
    row = data.accounts.loc[data.accounts["account_id"] == account_id]
    return row.iloc[0].to_dict() if not row.empty else {}


def _order_access_allowed(order_row: Dict[str, Any], ctx: Dict[str, str]) -> bool:
    if ctx["mode"] == "internal":
        return True
    return order_row.get("account_id") == ctx["account_id"]


def parse_order_id(text: str) -> Optional[str]:
    m = re.search(r"ORD-\d+", text.upper())
    return m.group(0) if m else None


def parse_ticket_id(text: str) -> Optional[str]:
    m = re.search(r"TKT-\d+", text.upper())
    return m.group(0) if m else None


def is_unsupported_exception_request(query: str) -> bool:
    ql = query.lower()
    asks_approval = any(w in ql for w in ["approve", "approval", "authorize", "allow", "grant"])
    asks_exception = any(w in ql for w in ["special", "exception", "override", "outside policy", "doesn't mention", "does not mention"])
    asks_nonstandard_action = any(w in ql for w in ["refund", "service credit", "credit", "waive", "compensation", "%"])
    return asks_approval and asks_nonstandard_action and asks_exception


def calculate_cancellation(data: ParcelPilotData, order_id: str, ctx: Dict[str, str]) -> ToolResult:
    row = data.orders.loc[data.orders["order_id"] == order_id]
    if row.empty:
        return ToolResult("structured_lookup", f"Order {order_id} not found", {"found": False})
    order = row.iloc[0].to_dict()
    if not _order_access_allowed(order, ctx):
        return ToolResult("structured_lookup", "Access denied for this order in current account context", {"found": False, "denied": True})

    acct = _get_account(data, order["account_id"])
    booked = pd.to_datetime(order["booked_at"])
    requested = pd.to_datetime(order["cancellation_requested_at"]) if pd.notna(order["cancellation_requested_at"]) else REFERENCE_TIME
    delta_mins = (requested - booked).total_seconds() / 60
    is_northstar = order["account_id"] == "ACCT-001"

    if str(order["status"]).upper() == "PICKED_UP":
        decision = "Cannot cancel after pickup. Recommend return-to-origin workflow."
        fee = None
        source = "03_Cancellation_and_Service_Credit_SOP_v4.pdf"
    elif is_northstar and str(order["status"]).upper() == "BOOKED":
        decision = "Eligible for cancellation with no fee due to Northstar agreement override."
        fee = 0
        source = "05_Northstar_Logistics_Enterprise_Agreement.pdf"
    elif str(order["status"]).upper() == "BOOKED":
        fee = 0 if delta_mins <= 30 else 250
        decision = "Eligible for cancellation." + (" No fee (within 30 min)." if fee == 0 else " INR 250 fee applies (after 30 min).")
        source = "03_Cancellation_and_Service_Credit_SOP_v4.pdf"
    else:
        decision = "Not cancellable in current status."
        fee = None
        source = "03_Cancellation_and_Service_Credit_SOP_v4.pdf"

    return ToolResult(
        "structured_lookup",
        f"Calculated cancellation outcome for {order_id}",
        {
            "found": True,
            "order": order,
            "account": acct,
            "decision": decision,
            "cancellation_fee_inr": fee,
            "minutes_since_booking": round(delta_mins, 1),
            "authoritative_source": source,
        },
    )


def calculate_service_credit(data: ParcelPilotData, order_id: str, ctx: Dict[str, str]) -> ToolResult:
    row = data.orders.loc[data.orders["order_id"] == order_id]
    if row.empty:
        return ToolResult("structured_lookup", f"Order {order_id} not found", {"found": False})
    order = row.iloc[0].to_dict()
    if not _order_access_allowed(order, ctx):
        return ToolResult("structured_lookup", "Access denied for this order in current account context", {"found": False, "denied": True})

    end = pd.to_datetime(order["pickup_window_end"])
    actual = pd.to_datetime(order["pickup_actual_at"]) if pd.notna(order["pickup_actual_at"]) else REFERENCE_TIME
    delay_hours = max(0, (actual - end).total_seconds() / 3600)

    carrier_fault = bool(order.get("carrier_fault"))
    customer_fault = bool(order.get("customer_fault"))

    threshold_hours = 2
    amount = min(500, float(order["shipment_fee_inr"]) * 0.1)
    source = "03_Cancellation_and_Service_Credit_SOP_v4.pdf"
    if order["account_id"] == "ACCT-002":
        threshold_hours = 4
        amount = 300
        source = "06_LumenWorks_Service_Agreement.pdf"

    if not carrier_fault or customer_fault:
        decision = "No credit should be promised; fault conditions are not met."
        eligible = False
    elif delay_hours > threshold_hours:
        decision = "Eligible for service credit."
        eligible = True
    else:
        decision = "Not eligible yet: delay threshold not met."
        eligible = False

    return ToolResult(
        "structured_lookup",
        f"Calculated service credit eligibility for {order_id}",
        {
            "found": True,
            "order": order,
            "eligible": eligible,
            "decision": decision,
            "credit_inr": round(amount, 2) if eligible else 0,
            "delay_hours": round(delay_hours, 2),
            "threshold_hours": threshold_hours,
            "authoritative_source": source,
        },
    )


def prepare_action(action_type: str, target: str, reason: str) -> ToolResult:
    return ToolResult(
        "state_change_prepare",
        f"Prepared {action_type} for {target}; awaiting explicit confirmation",
        {"pending_action": {"action_type": action_type, "target": target, "reason": reason}},
    )


def execute_action(action: Dict[str, str]) -> ToolResult:
    action_id = f"ACT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    result = {"action_id": action_id, **action, "status": "created"}
    return ToolResult("state_change_execute", f"Executed action {action_id}", result)


def summarize_sources(matches: List[Dict[str, Any]]) -> str:
    ordered = sorted(matches, key=lambda x: SOURCE_RANK.get(x["type"], 0), reverse=True)
    seen = []
    for m in ordered:
        label = f"{m['source']} ({m['type']})"
        if label not in seen:
            seen.append(label)
    return ", ".join(seen[:3])


def handle_query(data: ParcelPilotData, query: str, ctx: Dict[str, str]) -> Tuple[str, List[ToolResult], Optional[Dict[str, str]]]:
    tools: List[ToolResult] = []
    ql = query.lower()

    if is_unsupported_exception_request(query):
        tgt = parse_ticket_id(query) or parse_order_id(query) or ctx["account_id"]
        prep = prepare_action("escalation", tgt, f"Unsupported exception/approval request: {query}")
        tools.append(prep)
        msg = (
            "I can’t approve that special exception from the supplied policy/agreement data. "
            "This needs human support review. I prepared an escalation; reply 'confirm' to execute it or 'cancel' to discard."
        )
        return msg, tools, prep.payload["pending_action"]

    if any(w in ql for w in ["escalate", "create escalation", "update ticket", "follow-up", "follow up"]):
        tgt = parse_ticket_id(query) or parse_order_id(query) or "support-case"
        prep = prepare_action("escalation", tgt, "User requested escalation")
        tools.append(prep)
        msg = f"I prepared an escalation for {tgt}. Please reply 'confirm' to execute or 'cancel' to discard."
        return msg, tools, prep.payload["pending_action"]

    order_id = parse_order_id(query)
    if order_id and "cancel" in ql:
        doc = retrieve_documents(data, query, ctx)
        calc = calculate_cancellation(data, order_id, ctx)
        tools.extend([doc, calc])
        if calc.payload.get("denied"):
            return "I can’t access that order in this customer context.", tools, None
        if not calc.payload.get("found"):
            return f"I couldn't find {order_id}.", tools, None
        source_list = summarize_sources(doc.payload["matches"])
        p = calc.payload
        reply = (
            f"{p['decision']}\n\n"
            f"Order: {order_id} | Account: {p['order']['account_id']}\n"
            f"Minutes since booking at request time: {p['minutes_since_booking']}\n"
            f"Applied source precedence: agreement > current policy/SOP > product guide > deprecated/historical\n"
            f"Authoritative source used: {p['authoritative_source']}\n"
            f"Retrieved sources: {source_list}"
        )
        return reply, tools, None

    if order_id and ("credit" in ql or "late" in ql):
        doc = retrieve_documents(data, query, ctx)
        calc = calculate_service_credit(data, order_id, ctx)
        tools.extend([doc, calc])
        if calc.payload.get("denied"):
            return "I can’t access that order in this customer context.", tools, None
        if not calc.payload.get("found"):
            return f"I couldn't find {order_id}.", tools, None
        p = calc.payload
        source_list = summarize_sources(doc.payload["matches"])
        reply = (
            f"{p['decision']}\n\n"
            f"Delay: {p['delay_hours']}h (threshold: {p['threshold_hours']}h)\n"
            f"Proposed credit: INR {p['credit_inr']}\n"
            f"Authoritative source: {p['authoritative_source']}\n"
            f"Retrieved sources: {source_list}"
        )
        return reply, tools, None

    doc = retrieve_documents(data, query, ctx)
    tools.append(doc)
    best = doc.payload["matches"][0]
    caution = "\n\nNote: historical/deprecated sources are treated as low authority."
    reply = (
        "Here is the best available guidance from the supplied data pack:\n\n"
        f"{best['excerpt']}\n\n"
        f"Source: {best['source']} ({best['type']}){caution}"
    )
    if "who can access" in ql or "data" in ql and "account" in ql:
        reply += "\n\nCustomer mode is hard-scoped to one account in the data lookup layer."
    return reply, tools, None


def render_tool_trace(tool_results: List[ToolResult]) -> None:
    with st.expander("Tool trace", expanded=True):
        for t in tool_results:
            st.markdown(f"- **{t.name}**: {t.summary}")


def main() -> None:
    st.set_page_config(page_title="ParcelPilot Support Agent", layout="wide")
    st.title("ParcelPilot AI Support Agent")
    st.caption("Dataset snapshot reference time: 2026-08-16 11:00 Asia/Kolkata")

    data = ParcelPilotData()

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "pending_action" not in st.session_state:
        st.session_state.pending_action = None
    if "actions_log" not in st.session_state:
        st.session_state.actions_log = []

    with st.sidebar:
        st.header("Session Context")
        mode = st.selectbox("User context", ["customer", "internal"])
        if mode == "customer":
            account_id = st.selectbox("Customer account", data.accounts["account_id"].tolist())
            role = "customer"
        else:
            account_id = st.selectbox("Working account scope", ["ACCT-001", "ACCT-002", "ACCT-003", "ACCT-004"])
            role = st.selectbox("Internal role", ["support_agent", "ops_manager"])
        st.markdown("### Access Control")
        st.write("Enforced in data/tool layer; customer context cannot query other accounts.")
        st.markdown("### Mock Actions Executed")
        st.json(st.session_state.actions_log)

    ctx = account_context(data, mode, account_id, role)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("tools"):
                render_tool_trace(msg["tools"])

    user_input = st.chat_input("Ask about cancellations, service credits, ticket triage, or escalation.")
    if not user_input:
        return

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    if st.session_state.pending_action:
        answer = user_input.strip().lower()
        if answer in {"confirm", "yes", "approve"}:
            execution = execute_action(st.session_state.pending_action)
            st.session_state.actions_log.append(execution.payload)
            st.session_state.pending_action = None
            assistant_text = f"Confirmed and executed. Action ID: {execution.payload['action_id']}"
            tool_results = [execution]
        elif answer in {"cancel", "no", "discard"}:
            st.session_state.pending_action = None
            assistant_text = "Action discarded. No state change was executed."
            tool_results = []
        else:
            assistant_text = "I still need explicit confirmation. Reply 'confirm' to execute or 'cancel' to discard."
            tool_results = []
    else:
        assistant_text, tool_results, pending = handle_query(data, user_input, ctx)
        if pending:
            st.session_state.pending_action = pending

    st.session_state.messages.append({"role": "assistant", "content": assistant_text, "tools": tool_results})
    with st.chat_message("assistant"):
        st.markdown(assistant_text)
        if tool_results:
            render_tool_trace(tool_results)


if __name__ == "__main__":
    main()
