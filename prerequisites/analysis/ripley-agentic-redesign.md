# Agentic Re-Design — From 3 Agents to a Real Agentic System

**Author:** Ripley (Lead Architect)
**Date:** 2026-05-04
**Status:** Proposed (supersedes the PRD's 3-agent roster on acceptance)
**Trigger:** Kiko's challenge — *"¿Crees que con sólo 3 agentes resolvemos todo? Pensemos de forma transgresora para un enfoque agéntico de verdad."*

> **TL;DR.** Three agents was a sketch, not a design. A truly agentic pipeline for this problem is **6 agents at MVP** (Triage, Extractor, Coherence, Validator, Inventory, Communication) **+ 2 deferred** (Reconciliation in MVP+1, Learning in MVP+2). The 3-agent design bundles five distinct concerns into Agent 2 and the orchestrator, which is exactly the kind of monolithic "agent" trap that defeats the purpose of going agentic. This document justifies the new roster, rejects two tempting-but-unhelpful additions, and locks the MAF orchestration topology.

---

## 1. What's wrong with 3 agents

The PRD/ADR-v2 roster — Extractor, Validator, Inventory — is a **functional pipeline**, not an agentic system. The giveaway is that almost every interesting decision lives **outside** the agents:

| Concern | Where it lives in the 3-agent design | Problem |
|---|---|---|
| **Routing / triage** (auto-fast-track? HITL? hard reject?) | Hardcoded `if/else` in Durable orchestrator | No agent is responsible. Adding a new path (e.g., "trusted supplier auto-approve") means orchestrator code change and redeploy. |
| **Coherence / fraud / sanity checks** (PO exists, supplier real, dates plausible, prompt-injection markers) | Mixed into Agent 2's prompt alongside line-level Δ comparison | One prompt, two jobs, two failure modes. When validation fails you can't tell whether the PO was missing or qty was off. Different MCP scopes (BC-read only vs BC-read + Cosmos) collapsed into one agent. |
| **Outbound communication** (HITL email, 24h reminder, 48h escalation, ops alerts, future supplier notifications) | Activities fired directly from the orchestrator | Templates, recipient routing, channel selection (email vs Teams), and tone are baked into orchestrator code. Every new comm type = orchestrator deploy. |
| **End-of-day reconciliation** (drift between processed albaranes and BC posted receipts) | Not implemented | Silent failure mode. Discrepancies surface only when accounting closes the month. |
| **Pattern learning** (which suppliers degrade OCR? which line types cause discrepancies? what's the HITL approval-vs-reject ratio?) | Not implemented | The system has no memory across albaranes. Triage is forced to be naive. |
| **Supervision / fail-stop** (kill switch, circuit breaker on BC) | Implicit in Application Insights alerts | Reactive only. No agent is empowered to *stop* the pipeline. |

The result: 3 agents doing narrow LLM jobs, and a Durable orchestrator that ends up being a 4th, much smarter, *non-agentic* "agent" written in Python `if`-statements. **That defeats the point of MAF.**

The MAF SDK gives us free access to **Sequential + HandOff + GroupChat + Magentic** orchestration patterns. If we use it for nothing more than "Extractor → Validator → Inventory" we've bought a Ferrari to drive to the corner shop.

---

## 2. Decomposition principle

A concern deserves its own agent when **at least 3 of 5** are true:

1. **Distinct prompt / instruction set.** A single system prompt can't cleanly serve both jobs.
2. **Distinct tool scope.** Different MCP servers, different `require_approval` posture.
3. **Distinct failure mode.** When it goes wrong, the recovery path differs.
4. **Distinct cadence or trigger.** Per-albarán vs daily batch vs event-driven.
5. **Distinct ownership / governance.** Different reviewers, different change-control sensitivity.

Concerns that fail this test stay merged. Concerns that pass it become agents — even if they're rule-based and don't call an LLM. **In MAF an agent is just a `ChatAgent` with `tools=[...]`; an "agent" with deterministic tools and a degenerate prompt is a perfectly valid agent and gives us the same telemetry, identity, and orchestration surface as an LLM-driven one.**

---

## 3. The proposed roster — 6 + 2

### MVP roster (6 agents)

| # | Agent | Trigger | LLM | Primary tools | Why it's separate |
|---|---|---|---|---|---|
| **A1** | **Extractor** | `albaran.recibido` (Service Bus topic) | **GPT-5.1** (multimodal) | `content-understanding-mcp`, `document-intelligence` (fallback), Content Safety | Heavy multimodal model; only agent that needs GPT-5.1; only agent that touches the raw PDF. Pure transformer: PDF → strict JSON. |
| **A2** | **Triage** | `albaran.extraido` | **None at MVP** (rule-based; LLM optional MVP+1) | `cosmos-mcp` (read supplier reputation), `feature-flags-mcp` | Routing brain. Decides: fast-track (auto-approve), normal (Coherence→Validator), straight-to-HITL (low conf), or hard-reject (Content Safety hit). The decision *is* the agent's job — separate concern from any downstream agent. Rule-based first because explainability of routing decisions matters more than sophistication. |
| **A3** | **Coherence** | HandOff from Triage on "normal" path | **GPT-5-mini** | `bc-mcp-read` (PO + Vendor + Items), `cosmos-mcp` (read) | Pre-validation gate: does the PO exist and is it Open/Released? Is the supplier in BC's vendor master? Is the date in `[PO date, today + 7d]`? Are totals within an *order-of-magnitude* sanity envelope? Different prompt (sanity / fraud), different output (`coherence_ok: bool, reasons: []`), different escalation (suspicious → Communication ops alert, not HITL approval). Cheap, runs early, fail-fast. |
| **A4** | **Validator** | HandOff from Coherence on `coherence_ok=true` | **GPT-5-mini** | `bc-mcp-read` (PO Lines), `cosmos-mcp` (read) | Line-level Δ vs the PO at 2% tolerance — *only* job. Output: `{decision: coincide \| discrepancia, deltas[]}`. With Coherence split out, this prompt becomes ~⅓ shorter and the failure mode is unambiguous. |
| **A5** | **Inventory** | HandOff from Validator (`coincide`) **or** from Communication after `aprobado_hitl` | **GPT-5-mini** | `bc-mcp-write` (Post Purchase Receipt **only**, `require_approval=always` enforced server-side), `cosmos-mcp` (write) | The only agent with write access to BC. Narrow blast radius. `require_approval=always` is the hard guard. |
| **A6** | **Communication** | Event-driven on `albaran.discrepancia`, `albaran.baja_confianza`, `albaran.error_*`, `albaran.escalado`, internal timers | **GPT-5-mini** (only for tone-adjusting MODIFY/REJECT body text; templates otherwise) | `acs-email-mcp`, `cosmos-mcp` (read tienda config), `feature-flags-mcp` | Owns **all** outbound: HITL approval emails, 24h reminder, 48h escalation, 72h hard-cap ops alert, future supplier notifications. Decoupling this from the orchestrator means new comm types (e.g., supplier reject email, weekly digest, ops Slack) ship without touching the validation pipeline. |

### Deferred roster (2 agents, post-MVP)

| # | Agent | Cadence | LLM | When to add |
|---|---|---|---|---|
| **A7** | **Reconciliation** | ACA Job, cron 02:00 daily + weekly Sunday | **GPT-5-mini** (anomaly summarization only) | `bc-mcp-read` (Posted Receipts query), `cosmos-mcp` (read processed albaranes) | **MVP+1** — needed once the system runs in steady state. Compares last-N-days processed albaranes vs BC's actually-posted receipts, flags drift (posted but no albarán, albarán but no post, mismatched totals). Outputs anomaly bundle → Communication agent for ops digest. |
| **A8** | **Learning** | ACA Job, weekly Monday | **GPT-5-mini** (pattern summarization) | `cosmos-mcp` (read events), `cosmos-mcp` (write supplier-reputation doc) | **MVP+2** — only valuable once we have ≥4 weeks of data. Aggregates supplier OCR confidence trends, common discrepancy types, HITL approval/reject ratios. Writes a `supplier_reputation/<supplier_id>` doc that **Triage** then reads to make smarter routing decisions. This closes the agentic loop: the system learns. |

### Total: 6 at MVP, 8 at steady state.

---

## 4. Decisions I'm making and rejecting

### ✅ Adopted: Triage as a first-class agent (rule-based at MVP)

The decision branch in the orchestrator (`if estado in (baja_confianza, error_extraccion): HITL else: Validator`) is a routing policy. Routing policy belongs to a named, versioned, auditable component. Today it's three lines of Python; tomorrow it's "trusted-supplier fast-track if confianza ≥ 0.95 AND last 20 albaranes from this supplier had zero discrepancies AND total value < €500", which is exactly the kind of rule that needs change-control beyond a code review on the orchestrator.

Rule-based first (a `@tool`-decorated decision function plus a Cosmos-backed feature-flag table); LLM-based optional in MVP+1 once we have Learning Agent feeding it supplier reputation. Either way, **it's an agent**, with its own deployment artifact and telemetry span.

### ✅ Adopted: Coherence split from Validation

These are two jobs that happen to involve BC reads. Failure modes diverge: Coherence failures mean *something is wrong with the world* (missing PO, wrong supplier — needs ops attention), Validation failures mean *something is wrong with this albarán* (qty/price Δ — needs HITL). Bundling them was wrong from PRD day 1.

### ✅ Adopted: Communication as a dedicated agent (not an orchestrator activity)

HITL email isn't a "step in the workflow," it's a long-running side-channel that fires on multiple state-machine entries (`baja_confianza`, `discrepancia`, `error_validacion`, `error_inventario`), receives async callbacks, manages its own timers, and will eventually need to talk to suppliers and ops too. That's an agent's job. Putting it in the orchestrator means the orchestrator ends up owning email templates, which is wrong.

The agent uses **Service Bus scheduled messages** for the 24h/48h/72h timers (no Durable Functions — see ADR D‑R‑019), persists outbound state to Cosmos, and exposes a webhook endpoint (the email-action callback) as a separate ACA app that publishes `hitl.response` events back into the bus.

### ✅ Adopted: Reconciliation deferred to MVP+1, Learning deferred to MVP+2

Both are valuable, but neither is on the critical path for "PDF in, BC posted receipt out." Shipping MVP without them is honest; shipping MVP without the first 6 would be a fancy script with telemetry.

### ❌ Rejected: A "Supervisor" agent

Tempting (Magentic pattern lets us write one), but redundant. The MAF Sequential+HandOff topology *is* the supervisor. Adding a `SupervisorAgent` whose job is "watch the others" buys us nothing we don't get from App Insights + the Communication agent's ops-alert path. A separate supervisor agent only makes sense in fully-autonomous open-ended workflows (Magentic-style research agents); ours is a constrained, well-typed pipeline. **Telemetry + alerts + Communication's ops channel = supervision.** Don't build it.

### ❌ Rejected: A standalone "Fraud" agent

Fraud detection at our volume and risk profile (Verdecora, internal supplier base of ~200 known vendors) is **subsumed by Coherence + Learning**. Building a separate fraud agent before we have a learning loop is premature optimization. Revisit at MVP+3 if Communication's ops digest surfaces fraud-shaped patterns.

### ❌ Rejected: Foundry hosted/prompt agents

Confirmed by Kiko's directive (D‑R‑019 rewrite): **all agents run in ACA with the MAF SDK in-process.** Foundry is the model+telemetry endpoint, nothing more. This means:
- We get full HandOff (which is the whole point of going from 3→6 agents).
- We get a single deployment surface (ACA) and a single VNet integration story.
- We give up Foundry's `require_approval` server-side enforcement on tools — but we re-implement it via MAF's `@tool(approval_mode="always_require")` and Cosmos-backed approval state, which we needed anyway for HITL.

---

## 5. MAF orchestration topology

```
            Service Bus topic: albaran-events
                        │
   ┌────────────────────┼─────────────────────────────────────────┐
   │                    │                                         │
   ▼                    ▼                                         ▼
albaran.recibido   albaran.extraido                  albaran.discrepancia/error_*/escalado/baja_confianza
   │                    │                                         │
   ▼                    ▼                                         ▼
[A1 Extractor]     ┌──[A2 Triage]──┐                       [A6 Communication]
   (Sequential)    │    (HandOff)  │                       (Event-driven, standalone agent)
                   │               │                              │
                   ▼               ▼                              ▼
            [A3 Coherence]   "needs HITL"                   ACS Email + ACA webhook
                   │              ──────────▶ publishes  ───────────────────┐
                   │              albaran.baja_confianza /                  │
                   │              albaran.error_extraccion                  │
                   ▼                                                        │
            [A4 Validator]                                                  │
                   │                                                        │
        ┌──────────┴──────────┐                                             │
        ▼ "coincide"          ▼ "discrepancia"                              │
   [A5 Inventory]    publishes albaran.discrepancia ──────────▶ A6 ─────────┤
        │                                                                   │
        │            ◀── on hitl.response=aprobado_hitl ────────────────────┘
        ▼
   albaran.inventariado (terminal)
```

**Patterns used:**
- **`SequentialBuilder`** — A1 → A2 (single straight handoff after extraction).
- **`HandoffBuilder`** — A2 → {A3, A6} and A3 → A4 → {A5, A6}. The agents themselves choose the next hop based on instructions (per Ash's MAF research, §3.2). `require_per_service_call_history_persistence=True` on every participant, which is mandatory for HandOff.
- **Event-driven (Service Bus subscriber pattern)** — A6 (Communication) and the deferred A7/A8 are **not** in the HandOff workflow; they listen to topic events and run independently. A6 publishes back into the bus when HITL resolves, which triggers a new orchestration run that resumes at A5.
- **No Magentic, no GroupChat at MVP.** Both add nondeterminism we don't need on a regulated finance/inventory path.

**Why event-driven for Communication (not HandOff):**
HandOff is synchronous within a workflow run. HITL is hours-to-days asynchronous. Modeling A6 as a HandOff target would force us to keep workflow state in memory for 72h (impossible in ACA) or spill it to Cosmos and rebuild it on resume (which is what Durable Functions did for us before — and we just removed). The clean model is: A4/Triage **publishes a state-change event**, A6 **reacts** to it, and on resolution **publishes another event** that re-enters the pipeline at A5. State lives in Cosmos throughout. Service Bus scheduled messages carry the timers.

---

## 6. State machine impact

The 14-state machine from ADR-v2 §3 holds, with **two clarifications**:

1. **`baja_confianza` and `error_extraccion`** are now Triage's outputs, not Extractor's. Extractor publishes `albaran.extraido` with confianza score; Triage reads it and decides the state. This is cleaner because confidence-thresholds become a Triage policy concern, not an Extractor concern.
2. **`error_validacion`** (coherence failure — PO missing, supplier missing) is now Coherence Agent's terminal-or-HITL output, distinct from `discrepancia` (Validator's line-level Δ). Both route to A6 but with different email templates and different routing (coherence failures CC ops; line discrepancies do not).

No new states needed. The 14 states already accommodate the split.

---

## 7. Cost & complexity check

| Metric | 3-agent design | 6-agent MVP | Δ |
|---|---|---|---|
| LLM calls per albarán (happy path) | 3 | **3** | 0 |
| LLM calls per albarán (HITL path) | 2 (Extract + Validate; Inventory after approval) | **3** (Extract + Coherence + Validate; Inventory after approval) | +1 (GPT-5-mini, ~€0.001) |
| LLM calls (rejection path) | 2 | **2** (Extract + Coherence fails fast, no Validator) | -0 / sometimes -1 |
| Container Apps services | 5 (dispatcher, HITL webhook, 3 MCP servers) | **8** (one per agent + 3 MCP servers; some agents share an env, separate revisions) | +3 services, same env |
| Bicep modules | ~20 | ~26 | +6 |
| Telemetry spans per albarán | ~12 | ~18 | +6 (good — more visibility) |

**Triage is rule-based at MVP**, so it adds an ACA service but no LLM cost. Coherence adds one GPT-5-mini call (~€0.001 per albarán) but **saves a Validator call when coherence fails fast** (PO missing, supplier missing — historically ~3-5% of albaranes), so the steady-state delta is ~€0. The win is structural: failure modes are unambiguous and templates/policies are owned by the right component.

Communication agent is net-zero LLM cost (it sends emails; LLM only used for free-form modify/reject body text in <1% of cases).

**Verdict: complexity is +25%, agentic value is +200%, LLM cost is ≈ 0.**

---

## 8. Migration from ADR-v2

This redesign supersedes:
- ADR-v2 §1.3 component table rows 8/9/10 (3-agent definitions).
- ADR-v2 §1.4 hosting model (which placed agents in Foundry — rewritten by D‑R‑019).
- ADR-v2 §2.3 Flow 2 (which described a Durable Functions orchestrator with hardcoded if/else routing — rewritten as MAF HandOff in ACA).
- ADR-v2 §2.4 Flow 2b (HITL as a Durable sub-orchestrator — rewritten as Communication agent + Service Bus scheduled messages).

The ADR is updated in place with the new roster, hosting model, and decisions D‑R‑019 (rewritten) and D‑R‑020 through D‑R‑025.

---

## 9. Open items raised by this redesign

| # | Item | Owner | By |
|---|---|---|---|
| O‑11 | **Triage rule-set v1** — concrete thresholds for fast-track / normal / straight-to-HITL / hard-reject. Needs Lambert's input on Verdecora's risk tolerance. | Ripley + Lambert | Sprint 1 |
| O‑12 | **Communication agent's email-template inventory** — list every outbound type (HITL initial, 24h reminder, 48h escalation, 72h hard-cap ops alert, ops drift digest, future supplier reject). Templates owned in `infra/templates/`. | Newt + Lambert | Sprint 1 |
| O‑13 | **Service Bus scheduled message reliability** — confirm 72h scheduled-message TTL is supported on Standard tier in our region. (Premium guarantees longer; Standard is documented at "up to topic message TTL" which defaults to 14d — should be fine but verify.) | Brett | Sprint 0 close |
| O‑14 | **HandOff persistence in MAF + private VNet** — `require_per_service_call_history_persistence=True` requires somewhere to persist. Confirm whether MAF uses an in-memory store (acceptable for a single workflow run) or needs a backing store (then Cosmos). | Ash | Sprint 0 close |
| O‑15 | **Reconciliation Agent (A7) trigger design** — ACA Job + cron, but where does the cron live? KEDA cron scaler vs ACA Jobs `scheduleTriggerConfig`. Brett to pick. | Brett | MVP+1 planning |

---

*— Ripley, Lead Architect*
