# ParcelPilot AI Support Agent (Assessment Submission)

This repository contains a working AI support chatbot for the ParcelPilot assessment, built from the supplied candidate data pack.

## What is implemented

- A chat interface (Streamlit) that accepts natural-language requests.
- Tool-driven agent flow with visible tool trace:
  1. **Document search/retrieval** over supplied policy/SOP/agreement/product PDFs.
  2. **Structured lookup/calculation** over supplied `accounts`, `orders`, and `tickets` data.
  3. **State-changing action tool** (mocked escalation creation).
- **Mandatory explicit confirmation before action execution**.
- **Access control enforced in tool/data layer**:
  - Customer mode is hard-scoped to one customer account.
  - Internal mode is available for authorised staff context.
- **Source reliability and conflict handling**:
  - Authority order: customer agreement > current policy/SOP > current product guide > deprecated policy/historical context.
  - Deprecated/historical guidance is treated as low authority.

## Minimum requirements mapping

1. **Chatbot + natural-language queries**: done (`app.py`, Streamlit chat).
2. **Access control and privacy**: done via mode/account scoping in lookup layer.
3. **At least three tools**: done (doc retrieval, structured calculation, state action).
4. **Confirmation before actions**: done (`confirm` needed before execution).
5. **Multi-step requests**: done (example: cancellation/service-credit flows combine retrieval + account/order lookup + policy/contract logic).
6. **Interface + tool visibility**: done (chat UI + tool trace panel).

---

## Setup and run

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Run app

```bash
streamlit run app.py
```

The app automatically extracts the candidate ZIP into `data_pack/` on first run.

---

## Example queries

- `Can Northstar cancel ORD-1001 without a cancellation fee? Explain why.`
- `Is ORD-2002 eligible for a service credit?`
- `Escalate TKT-501 because all shipment creation is failing.`
  - Then reply `confirm` to execute the mocked state change.

---

## Architecture Note

### Agent design
- Single orchestrator that interprets user input and selects one or more tools.
- Session memory stores pending actions and chat history.

### Tool design
- **Document search**: TF-IDF retrieval over text extracted from supplied PDFs.
- **Structured data tool**: policy-aware calculations (cancellation fees, service credit eligibility) using workbook data.
- **Action tool**: mock state mutation with two-phase commit style (`prepare` -> explicit `confirm` -> `execute`).

### Document + structured data handling
- PDF text is extracted via `pypdf` and indexed.
- Excel sheets are loaded with `pandas` from the supplied workbook.
- Dataset snapshot time is fixed to workbook README timestamp (`2026-08-16 11:00 Asia/Kolkata`) for time-based logic.

### Source reliability and conflict handling
- Explicit precedence is encoded and surfaced in responses.
- Contract overrides are applied before default policy/SOP rules.
- Deprecated policy and historical ticket guidance are treated as context only.

### Major technical trade-offs
- Chose local deterministic retrieval/rules over external hosted LLM APIs to keep the submission runnable with no secrets.
- Kept action writes mocked but confirmation-gated to satisfy safe state-change behavior.

---

## Product Note

### Additional client problem chosen
**Problem 2: Trust and reliability** was addressed directly:
- Explicit source precedence.
- Contract override handling.
- Confirmation gate before state-changing actions.
- Conservative responses when authority is weak or access is denied.

### What else I would build next (prioritized)
1. SLA breach monitor + proactive incident clustering dashboard for internal teams.
2. Retrieval quality evaluator with golden test set + confidence scoring.
3. Role-based auth integration (SSO + audit logs) for production-grade access controls.
4. Human handoff workflow with complete evidence package.

### What was intentionally left out
- Production authentication/authorization backend (mocked context used).
- Real ticketing-system/API integrations for true writes (action tool is local mock).
- Hosted deployment and video recording artifacts (not included in this repo snapshot).

### One metric to judge usefulness
- **Deflection with quality guardrail**: percentage of support queries resolved without human handoff while maintaining low correction rate from support agents.

---

## AI tool usage

- Used AI coding assistance to scaffold and refine the Streamlit agent structure, tool orchestration, and documentation.
- Used AI assistance for fast iteration on policy-rule wiring, response structure, and requirement coverage checks.
