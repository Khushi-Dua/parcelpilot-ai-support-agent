# ParcelPilot AI Support Agent

This repository contains a working AI support chatbot built for the CalQuity AI Engineer assessment. The application uses the supplied ParcelPilot candidate data pack and supports both customer-facing and authorised internal support workflows.

## Live Application

**Streamlit:** https://parcelpilot-ai-support-agent-khushi-dua.streamlit.app/

## What is implemented

* A **Streamlit chat interface** that accepts natural-language support requests.
* A tool-driven agent workflow with visible tool traces:

  1. **Document search/retrieval** over the supplied policy, SOP, agreement, and product-operation documents.
  2. **Structured lookup/calculation** over the supplied account, order, and ticket data.
  3. **State-changing action tool** for mocked support escalations.
* **Explicit confirmation before state-changing actions**:
  `prepare → confirm → execute`
* **Access control enforced at the data/tool layer**:

  * Customer mode is scoped to the selected customer account.
  * Customer-specific agreement retrieval is account-scoped before document ranking/retrieval.
  * Internal mode supports authorised ParcelPilot staff workflows.
* **Source reliability and conflict handling**:

  * Customer agreement > current policy/SOP > current product guide > deprecated/historical context.
  * Deprecated and historical guidance is treated as lower-authority context.
  * Unsupported exceptions and requests requiring human judgment are escalated rather than answered with fabricated guidance.

## Repository Structure

```text
parcelpilot-ai-support-agent/
├── app.py
├── requirements.txt
├── README.md
├── CalQuity AI Engineer — Job Description & AI Agent Assessment.pdf
└── data_pack/
    └── AI Agent Assessment - Candidate Pack/
        ├── 01_Support_Policy_v3_CURRENT.pdf
        ├── 02_Support_Policy_v2_DEPRECATED.pdf
        ├── 03_Cancellation_and_Service_Credit_SOP_v4.pdf
        ├── 04_Product_Operations_Guide_and_Known_Issues.pdf
        ├── 05_Northstar_Logistics_Enterprise_Agreement.pdf
        ├── 06_LumenWorks_Service_Agreement.pdf
        └── ParcelPilot_Assessment_Data.xlsx
```

## Minimum Requirements Mapping

| Assessment requirement             | Implementation                                                                     |
| ---------------------------------- | ---------------------------------------------------------------------------------- |
| Chatbot + natural-language queries | Streamlit chat interface in `app.py`                                               |
| Supplied-data grounding            | Uses the supplied PDFs and `ParcelPilot_Assessment_Data.xlsx`                      |
| Access control and privacy         | Account-scoped customer retrieval and structured-data checks                       |
| Document search/retrieval          | TF-IDF retrieval over supplied PDF text                                            |
| Structured lookup/calculation      | Workbook-based account, order, ticket and policy calculations                      |
| State-changing action              | Mock escalation creation                                                           |
| Confirmation before actions        | `prepare → confirm → execute`                                                      |
| Multi-step requests                | Combines document retrieval, structured lookup, source precedence and calculations |
| Tool visibility                    | Expandable tool trace shown for agent actions                                      |

## Setup and Run

### 1. Clone the repository

```bash
git clone https://github.com/Khushi-Dua/parcelpilot-ai-support-agent.git
cd parcelpilot-ai-support-agent
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the application

```bash
streamlit run app.py
```

The application reads the candidate data pack from:

```text
data_pack/AI Agent Assessment - Candidate Pack/
```

No external LLM API key is required for the submitted implementation.

## Example Queries

### Cancellation / contract precedence

```text
Can Northstar cancel ORD-1001 without a cancellation fee? Explain why.
```

### Service-credit calculation

```text
Is ORD-2002 eligible for a service credit? Explain the calculation and source.
```

### Escalation

```text
Escalate TKT-501 because all shipment creation is failing.
```

The agent prepares the escalation first and requires the user to reply:

```text
confirm
```

before the mocked state-changing action is executed.

### Unsupported exception / human review

```text
Can you approve a special 50% refund for this customer even though the agreement doesn't mention it?
```

The agent does not invent an approval. It identifies the request as an unsupported exception, requires human review, and prepares an escalation subject to confirmation.

## Architecture Note

### Agent Design

The application uses a single orchestration layer that interprets the user's request, determines the appropriate workflow, and invokes the required tools.

Session state stores chat history and pending state-changing actions so that confirmation is handled as a separate step.

### Tool Design

#### 1. Document Search

A local TF-IDF retrieval pipeline searches text extracted from the supplied PDFs.

It covers:

* current policies
* deprecated policies
* cancellation/service-credit SOP
* product operations documentation
* customer agreements

Customer-specific agreement documents are account-scoped before ranking and retrieval when the user is in customer mode.

#### 2. Structured Data Lookup / Calculation

The supplied Excel workbook is loaded with `pandas` and used for:

* account lookups
* order lookups
* ticket information
* cancellation calculations
* service-credit calculations
* account-scope validation

The dataset snapshot reference time is taken from the supplied workbook README:

```text
2026-08-16 11:00 Asia/Kolkata
```

#### 3. State-Changing Action

State-changing operations are mocked locally using a two-phase flow:

```text
prepare → explicit confirmation → execute
```

This prevents an action from executing before the user explicitly confirms it.

## Access Control

The application supports two contexts:

### Customer

Customer users are scoped to the selected customer account.

Customer-specific orders, tickets, and agreements belonging to other accounts cannot be accessed.

### Internal

Authorised internal support users can work with operational data according to the selected internal account scope and role.

Access control is enforced inside the data/tool layer rather than relying only on model instructions.

## Source Reliability and Conflict Handling

The source hierarchy is:

```text
Customer agreement
        ↓
Current policy / SOP
        ↓
Current product guide
        ↓
Deprecated / historical context
```

When sources disagree:

* customer-specific agreement terms take precedence where applicable
* current policy/SOP is preferred over deprecated guidance
* historical ticket resolutions are treated as context rather than authoritative instructions
* the authoritative source is surfaced in the response
* unsupported or uncertain requests are escalated instead of being guessed

## Trust & Reliability

The additional client problem selected for this submission is:

**Problem 2: Trust and Reliability**

The implementation addresses this through:

* explicit source precedence
* customer-agreement overrides
* account-level access control
* visible source/tool traces
* conservative handling of unsupported exceptions
* human escalation when the system cannot confidently or legitimately complete a request
* confirmation before state-changing actions

## Technical Trade-offs

### Deterministic local retrieval

The submission uses local TF-IDF retrieval and rule-based workflow logic rather than relying on an external hosted LLM API.

This keeps the application:

* self-contained
* reproducible
* inexpensive to run
* free from external API secrets
* grounded in the supplied assessment data

### Mocked actions

Ticket/escalation writes are mocked locally rather than connected to a real ticketing system. This keeps the assessment implementation safe while still demonstrating a confirmation-gated state-changing workflow.

## Product Note

### Additional Client Problem Chosen

**Trust and Reliability**

This was prioritised because incorrect answers or actions can quickly reduce support-team trust.

The implementation therefore prioritises:

* source reliability
* agreement/policy precedence
* access control
* uncertainty handling
* human escalation
* confirmation before actions

### What I Would Build Next

1. **Proactive SLA and incident monitoring**

   * Identify SLA breaches and recurring issues before a support agent asks about them.

2. **Retrieval evaluation and confidence scoring**

   * Maintain a golden test set and continuously measure retrieval quality.

3. **Production authentication and audit logging**

   * Replace the mocked context with SSO, role-based permissions, and audit trails.

4. **Human handoff workflow**

   * Provide support agents with a complete evidence package containing the relevant order, documents, calculations, and tool traces.

### Intentionally Left Out

* Production authentication/authorization infrastructure
* Real ticketing-system/API integrations
* Production-grade monitoring and observability
* Proactive issue-detection dashboard

These were intentionally kept outside the assessment scope to focus on the required agent, retrieval, access-control, reliability, and confirmation workflows.

### Success Metric

**Deflection with a quality guardrail**

Percentage of support queries resolved without human handoff while maintaining a low correction rate from support agents.

## Demo Video

A roughly 5-minute demonstration covers:

1. Solution architecture and tool design
2. Northstar cancellation and source precedence
3. Customer vs internal access control
4. Service-credit calculation
5. Unsupported exception escalation
6. Confirmation-gated state-changing action
7. Key technical and product decisions

**Demo video:** *Add final video link here after recording.*

## AI Tool Usage

GitHub Copilot was used selectively for minor coding assistance and debugging during development.

All final implementation decisions and testing were performed against the supplied assessment requirements and dataset.

## Assessment Deliverables

* **Repository:** https://github.com/Khushi-Dua/parcelpilot-ai-support-agent
* **Hosted application:** https://parcelpilot-ai-support-agent-khushi-dua.streamlit.app/
* **Demo video:** *Add final video link here*
* **Architecture note:** Included in this README
* **Product note:** Included in this README
* **AI tool usage:** Included in this README
