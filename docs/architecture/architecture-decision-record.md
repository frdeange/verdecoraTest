# Architecture Decision Record — Sistema Inteligente de Gestión de Albaranes

> **Status:** v3 — Definitive (replaces PRD §3, §4, §10 and ADR-v2 hosting model + agent roster)
> **Author:** Ripley (Lead Architect)
> **Date:** 2026-05-04
> **Project:** Verdecora — Albaranes ingestion, validation, and BC inventory automation
> **Stack:** Python 3.12, Microsoft Agent Framework (MAF) v1.0+ SDK, Azure OpenAI (via Foundry), Azure Container Apps (sole compute plane), Cosmos DB NoSQL, Service Bus (incl. scheduled messages for timers), Azure Communication Services Email, Business Central Online (MCP-enabled)
> **Region:** **Sweden Central** (single primary region; DR design TBD post‑MVP)

This document supersedes the PRD's architecture sections and is the single source of architectural truth going forward. It incorporates all answers to Q1–Q12, the private‑networking requirement, the ACS Email HITL channel directive (2026‑05‑03 22:45), the **all-ACA + Service Bus, no Durable Functions** directive (2026‑05‑03 23:07/23:10), and the **6‑agent agentic redesign** (Ripley, 2026‑05‑04 — see `prerequisites/analysis/ripley-agentic-redesign.md`). References to detailed analyses live in `prerequisites/analysis/`.

> **What changed vs ADR‑v2 (read this first):**
> 1. **All Durable Functions removed.** Compute is **single-plane ACA**. Timers are **Service Bus scheduled messages**. State lives in **Cosmos**. (D‑R‑019 rewritten.)
> 2. **All agents run in ACA with the MAF SDK in‑process.** Foundry is a **model + telemetry endpoint** only (Azure OpenAI behind it). No Foundry-hosted agents. MAF orchestrates HandOff between agents. (D‑R‑019.)
> 3. **HITL channel = Azure Communication Services Email + ACA web form.** No WorkIQ, no Power Automate, no Teams bot. (D‑R‑004 rewritten.)
> 4. **Agent roster expanded from 3 to 6** (Triage, Extractor, Coherence, Validator, Inventory, Communication) with 2 deferred (Reconciliation MVP+1, Learning MVP+2). (D‑R‑020.)

---

## 1. Architecture Overview

### 1.1 Context (one paragraph)

Verdecora's in‑store capture app already exists and produces a PDF of each albarán that lands in Azure Blob Storage. The PDF carries the BC purchase‑order number on every albarán (no fuzzy matching). Our system picks up from that Blob event, extracts structured data with a multimodal agent, **routes** the result through a Triage agent, **sanity-checks** it against BC master data with a Coherence agent, **reconciles** it against the PO line-by-line with a Validator agent, sends discrepancies to a human via **ACS Email + an ACA-hosted web form** (handled by a dedicated Communication agent), and on approval posts the receipt to Business Central via the **native BC MCP server** (Inventory agent). All compute runs in **Azure Container Apps** using the **MAF SDK in-process**; Azure OpenAI (accessed via the Foundry project) provides model endpoints only. All infrastructure is deployed inside a **private VNet in Sweden Central**, with self‑hosted GitHub runners (in ACA Jobs) as the only egress path into private resources.

### 1.2 System diagram (logical, ASCII)

```
                            ┌─────────────────────────────────────────────────┐
                            │            VERDECORA TIENDAS (×25)              │
                            │   [Existing capture app]  ──PDF── ▶  HTTPS      │
                            └──────────────────────────┬──────────────────────┘
                                                       │
                                                       ▼  (Private Endpoint)
┌────────────────────────────────────────────────────────────────────────────────────┐
│                       AZURE — SWEDEN CENTRAL — PRIVATE VNET                        │
│                                                                                    │
│  ┌────────────── Flow 0: Ingestion & Dedup (ACA Job, KEDA) ───────────────────┐  │
│  │  Blob Storage (albaranes-raw/yyyy/mm/tienda_id/) ──┐                       │  │
│  │       │                                             ▼                       │  │
│  │       │                                   Event Grid (BlobCreated)          │  │
│  │       │                                             │                       │  │
│  │       │                                             ▼                       │  │
│  │       │                              Service Bus queue: extraccion-in       │  │
│  │       │                                             │                       │  │
│  │       │                                             ▼                       │  │
│  │       │                       ACA Job (KEDA on queue length)                │  │
│  │       │                       └─ Dedup check (blob_etag, supplier,          │  │
│  │       │                          albaran_number) vs Cosmos                  │  │
│  │       │                          → if dup → estado=duplicado, ack           │  │
│  │       │                          → else → estado=recibido, publish          │  │
│  │       │                                   albaran.recibido on bus topic     │  │
│  └───────┴────────────────────────────────────────────────────────────────────┘  │
│                                                                                    │
│  ┌──────────── Flow 1+2: Agentic pipeline (ACA, MAF SDK in-process) ──────────┐  │
│  │                                                                             │  │
│  │   Service Bus topic: albaran-events                                         │  │
│  │           │                                                                 │  │
│  │           ▼ (subscription: albaran.recibido)                                │  │
│  │   ┌─────────────────────────────────────────────────────────────────┐      │  │
│  │   │  ACA Container App: agentic-orchestrator (KEDA)                 │      │  │
│  │   │  Python process running MAF orchestration:                      │      │  │
│  │   │                                                                 │      │  │
│  │   │   ┌────────────────────── SequentialBuilder ───────────────┐    │      │  │
│  │   │   │                                                         │    │      │  │
│  │   │   │   [A1 Extractor]   GPT-5.1 (multimodal)                │    │      │  │
│  │   │   │     ├─ MCPStreamableHTTPTool: content-understanding    │    │      │  │
│  │   │   │     ├─ MCPStreamableHTTPTool: document-intelligence    │    │      │  │
│  │   │   │     └─ Content Safety pre-scan                         │    │      │  │
│  │   │   │                  │                                      │    │      │  │
│  │   │   │                  ▼                                      │    │      │  │
│  │   │   │   ┌──────────── HandoffBuilder ──────────────────────┐  │    │      │  │
│  │   │   │   │                                                  │  │    │      │  │
│  │   │   │   │   [A2 Triage]   GPT-5-mini structured output    │  │    │      │  │
│  │   │   │   │     ├─ strict JSON: {route, reasoning}          │  │    │      │  │
│  │   │   │   │     └─ MCP: cosmos-mcp (read supplier rep)      │  │    │      │  │
│  │   │   │   │              │                                  │  │    │      │  │
│  │   │   │   │     ┌────────┼─────────┬─────────────┐          │  │    │      │  │
│  │   │   │   │     ▼        ▼         ▼             ▼          │  │    │      │  │
│  │   │   │   │  fast-track normal  HITL-direct  hard-reject    │  │    │      │  │
│  │   │   │   │     │        │         │             │          │  │    │      │  │
│  │   │   │   │     │        ▼         │             │          │  │    │      │  │
│  │   │   │   │     │ [A3 Coherence]   │             │          │  │    │      │  │
│  │   │   │   │     │   GPT-5-mini     │             │          │  │    │      │  │
│  │   │   │   │     │   ├─ bc-mcp-read │             │          │  │    │      │  │
│  │   │   │   │     │   └─ cosmos read │             │          │  │    │      │  │
│  │   │   │   │     │        │         │             │          │  │    │      │  │
│  │   │   │   │     │   coherence_ok? coherence_fail │          │  │    │      │  │
│  │   │   │   │     │        │             │         │          │  │    │      │  │
│  │   │   │   │     │        ▼             │         │          │  │    │      │  │
│  │   │   │   │     │  [A4 Validator]      │         │          │  │    │      │  │
│  │   │   │   │     │   GPT-5-mini         │         │          │  │    │      │  │
│  │   │   │   │     │   ├─ bc-mcp-read     │         │          │  │    │      │  │
│  │   │   │   │     │   └─ cosmos read     │         │          │  │    │      │  │
│  │   │   │   │     │        │             │         │          │  │    │      │  │
│  │   │   │   │     │  ┌─────┴─────┐       │         │          │  │    │      │  │
│  │   │   │   │     │  ▼           ▼       │         │          │  │    │      │  │
│  │   │   │   │     │ coincide  discrep.   │         │          │  │    │      │  │
│  │   │   │   │     │  │           │       │         │          │  │    │      │  │
│  │   │   │   │     ▼  ▼           ▼       ▼         ▼          │  │    │      │  │
│  │   │   │   │  [A5 Inventory]   publish events on Service Bus │  │    │      │  │
│  │   │   │   │   GPT-5-mini      → albaran.discrepancia        │  │    │      │  │
│  │   │   │   │   bc-mcp-write    → albaran.error_validacion    │  │    │      │  │
│  │   │   │   │   (Post Receipt)  → albaran.baja_confianza      │  │    │      │  │
│  │   │   │   │   require_approval                               │  │    │      │  │
│  │   │   │   │   = always (MAF)                                 │  │    │      │  │
│  │   │   │   └──────────────────────────────────────────────────┘  │    │      │  │
│  │   │   │              │                                           │    │      │  │
│  │   │   │              ▼                                           │    │      │  │
│  │   │   │      albaran.inventariado (terminal)                     │    │      │  │
│  │   │   └──────────────────────────────────────────────────────────┘    │      │  │
│  │   └─────────────────────────────────────────────────────────────────┘      │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                    │
│  ┌──────────── Flow 3: Communication Agent (event-driven, ACA) ─────────────────┐│
│  │   Service Bus topic subscriptions:                                            ││
│  │     albaran.discrepancia | .baja_confianza | .error_validacion | .escalado    ││
│  │                                │                                              ││
│  │                                ▼                                              ││
│  │   ┌───────── ACA Container App: communication-agent ──────────┐               ││
│  │   │ MAF ChatAgent (GPT-5-mini, used only for MODIFY/REJECT     │               ││
│  │   │   tone-adjusting body text; templates for everything else) │               ││
│  │   │   ├─ MCP: acs-email-mcp (Azure Communication Services)     │               ││
│  │   │   ├─ MCP: cosmos-mcp (read tienda config + write hitl log) │               ││
│  │   │   └─ Service Bus client: schedule reminder/escalation msgs │               ││
│  │   └────────────────────────────────────────────────────────────┘               ││
│  │                                │                                              ││
│  │     Sends ACS email with ACCEPT/REJECT/MODIFY deep links to →                 ││
│  │                                ▼                                              ││
│  │   ┌──────── ACA Container App: hitl-webform (FastAPI) ────────┐               ││
│  │   │  Receives the human's button-click / form submission.     │               ││
│  │   │  Persists decision to Cosmos and publishes:               │               ││
│  │   │    hitl.response.{aprobado_hitl|rechazado|modificado}     │               ││
│  │   │  back into albaran-events topic.                          │               ││
│  │   └────────────────────────────────────────────────────────────┘               ││
│  │                                │                                              ││
│  │   Timers: Service Bus scheduled messages with                                 ││
│  │     ScheduledEnqueueTime = now + 24h / 48h / 72h.                             ││
│  │     If hitl.response arrives first → cancel scheduled msg.                    ││
│  │     Else → A6 fires reminder / escalation / hard-cap ops alert.               ││
│  │                                                                               ││
│  │   Resume: hitl.response.aprobado_hitl re-enters orchestrator on the           ││
│  │     "resume-at-A5" subscription → A5 Inventory runs.                          ││
│  └───────────────────────────────────────────────────────────────────────────────┘│
│                                                                                    │
│  ┌─────────────────── Cross-cutting platform services ──────────────────────────┐│
│  │  Azure OpenAI (via Foundry project) — model endpoints only (GPT-5.1, 5-mini) ││
│  │     · Foundry provides: model catalog, deployments, traces, evals             ││
│  │     · Foundry does NOT host agents in this design                             ││
│  │  Private MCP servers in ACA: cosmos-mcp, content-understanding-mcp,           ││
│  │     acs-email-mcp, feature-flags-mcp                                          ││
│  │  Native BC MCP (read + scoped write) — Microsoft-managed, OAuth2 PKCE         ││
│  │  Azure Key Vault (no shared keys; Managed Identity everywhere)                ││
│  │  App Insights + Log Analytics (OTel GenAI conventions; albaran_id = trace_id) ││
│  │  Self-hosted GitHub runners (ACA Jobs) — only deployment path                 ││
│  │  Private Endpoints for: Blob, Cosmos, Service Bus, Key Vault, Foundry, ACA   ││
│  │  Egress: Azure Firewall or NAT Gateway (Brett owns)                           ││
│  └───────────────────────────────────────────────────────────────────────────────┘│
│                                                                                    │
│  ┌─────────────── Deferred (post-MVP) ──────────────────────────────────────────┐│
│  │  [A7 Reconciliation]  ACA Job, cron daily 02:00 + weekly Sunday  (MVP+1)     ││
│  │  [A8 Learning]        ACA Job, cron weekly Monday → supplier reputation Cosmos│
│  └───────────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────┬─────────────────────────────────────────────────────┘
                               │ Private Link / VNet integration
                               ▼
                    Business Central Online (MCP enabled)
                    Tenant: 562029ef-9022-45a6-b255-40cd71ebb2ce
                    Env: Production · Company: CRONUS USA Inc.
```

### 1.3 Component table (replaces PRD §3.1 and ADR-v2 §1.3)

| # | Component | Service / Tech | Purpose | Notes |
|---|---|---|---|---|
| 1 | Capture app | Pre‑existing (Verdecora) | Generates PDF, uploads to Blob | **Out of scope.** API contract: PDF + metadata `{tienda_id, captured_at, user_upn}` |
| 2 | Blob Storage | `albaraneststXXXX` (Standard ZRS, hierarchical NS) | Raw + processed PDFs | Container `albaranes-raw/yyyy/mm/tienda_id/` ; **6‑year retention (legal hold + immutable policy)** |
| 3 | Event Grid | System topic on Storage Account | `BlobCreated` notification | Filtered to `albaranes-raw/` prefix |
| 4 | Service Bus | Standard tier, namespace `sb-albaranes-prd` | `extraccion-in` queue + `albaran-events` topic + **scheduled messages for 24h/48h/72h timers** | DLQ on every entity; sessions disabled |
| 5 | Container Apps environment | Internal (VNet‑only) | **Sole compute plane.** Hosts: Flow 0 dedup ACA Job, agentic-orchestrator app (A1–A5), communication-agent app (A6), HITL webform, private MCP servers. | Workload profile: Consumption (default) + 1 Dedicated D4 for `agentic-orchestrator` (multimodal upload/response on A1) |
| 6 | **`agentic-orchestrator`** ACA app | Python 3.12 + MAF SDK in‑process | Runs `SequentialBuilder([A1]).then(HandoffBuilder([A2,A3,A4,A5]))`. KEDA scaler on Service Bus subscription `albaran.recibido`. | One container instance handles one albarán end-to-end through agents A1–A5; HITL bounces out via event publish, comes back via separate "resume-at-A5" subscription. |
| 7 | **`communication-agent`** ACA app | Python 3.12 + MAF SDK | A6 — owns ALL outbound (HITL emails, reminders, escalations, ops alerts). KEDA scaler on multiple Service Bus subscriptions (`albaran.discrepancia`, `.baja_confianza`, `.error_validacion`, `.escalado`, `.error_inventario`, plus reminder/escalation scheduled-message triggers). | Schedules reminder/escalation via Service Bus scheduled messages. Cancels them when `hitl.response.*` arrives first. |
| 8 | **`hitl-webform`** ACA app | Python 3.12 (FastAPI) | Receives ACS-email button-click / form submission, persists decision, publishes `hitl.response.{aprobado_hitl|rechazado|modificado}`. | Internal ingress + Front-Door / APIM in front for human reachability over corporate identity. |
| 9 | Azure OpenAI (via Foundry project) | `foundry-albaranes-prd` (private networking) | **Model endpoints + telemetry only.** Two deployments: `gpt-5.1` (multimodal) and `gpt-5-mini`. | Foundry does NOT host agents in this design. Foundry traces still capture model-call telemetry. |
| 10 | **A1 — Extractor agent** | MAF `ChatAgent` in `agentic-orchestrator`, GPT‑5.1 | PDF → strict JSON | Tools: `content-understanding-mcp`, `document-intelligence` (fallback), Content Safety pre-scan. Strict JSON schema; no parallel tool calls. |
| 11 | **A2 — Triage agent** | MAF `ChatAgent` in `agentic-orchestrator`, **GPT‑5‑mini + structured output (strict JSON schema: `{route, reasoning}`)** | Routes albarán: fast-track / normal / direct-HITL / hard-reject | Rules are provided as system-prompt context; `cosmos-mcp` supplies supplier reputation. Routing policy versioned in `infra/policies/triage/`. |
| 12 | **A3 — Coherence agent** | MAF `ChatAgent` in `agentic-orchestrator`, GPT‑5‑mini | Sanity gate: PO exists, supplier valid, dates plausible, totals in envelope | Tools: `bc-mcp-read`, `cosmos-mcp` (read). Output: `{coherence_ok, reasons[]}`. Failures route to A6 with ops CC, NOT to HITL approval. |
| 13 | **A4 — Validator agent** | MAF `ChatAgent` in `agentic-orchestrator`, GPT‑5‑mini | Line-level Δ vs PO at 2% tolerance | Tools: `bc-mcp-read`, `cosmos-mcp` (read). Output: `{decision: coincide \| discrepancia, deltas[]}`. |
| 14 | **A5 — Inventory agent** | MAF `ChatAgent` in `agentic-orchestrator`, GPT‑5‑mini | Posts Purchase Receipt to BC | Tools: `bc-mcp-write` (Post Purchase Receipt **only**, `@tool(approval_mode="always_require")` enforced via MAF + Cosmos approval table), `cosmos-mcp` (write). |
| 15 | **A6 — Communication agent** | MAF `ChatAgent` in `communication-agent` app, GPT‑5‑mini | All outbound: HITL email, reminders, escalations, ops alerts. LLM only for MODIFY/REJECT body text; templates otherwise. | Tools: `acs-email-mcp` (Azure Communication Services), `cosmos-mcp` (read tienda config + write hitl audit), Service Bus client (schedule + cancel scheduled messages). |
| 16 | **A7 — Reconciliation agent** *(deferred MVP+1)* | MAF `ChatAgent` in ACA Job, GPT‑5‑mini | Daily/weekly drift check between processed albaranes and BC posted receipts | Tools: `bc-mcp-read` (Posted Purchase Receipts), `cosmos-mcp` (read). Output: anomaly bundle → publish to A6 for ops digest. |
| 17 | **A8 — Learning agent** *(deferred MVP+2)* | MAF `ChatAgent` in ACA Job, GPT‑5‑mini | Weekly pattern aggregation: supplier OCR confidence, discrepancy types, HITL ratios | Tools: `cosmos-mcp` (read events + write `supplier_reputation/<supplier_id>`). Closes the agentic loop: A2 reads what A8 writes. |
| 18 | Azure AI Content Understanding | Primary OCR | Heterogeneous albaranes | Decision pending Sprint 0 benchmark vs DI |
| 19 | Document Intelligence v4.0 | Fallback OCR | Stable suppliers + CU‑GA hedge | Deploy but do not light up by default |
| 20 | Cosmos DB NoSQL | `cosmos-albaranes-prd` | Aggregate store + read‑models + HITL approval state + supplier reputation | Containers: `albaranes` (PK `/pk = tienda_id_yyyymm`), `tiendas` (PK `/tienda_id`), `hitl_approvals` (PK `/albaran_id`), `supplier_reputation` (PK `/supplier_id`), `dlq` |
| 21 | BC native MCP (read) | Business Central Online | PO + Vendor + Items + Posted Receipts read | OAuth2 Auth Code + PKCE, delegated identity. Tenant `562029ef-…`, env Production, company CRONUS USA Inc. |
| 22 | BC native MCP (write) | Same BC tenant, separate scoped config | Post Purchase Receipt only | **No DELETE.** |
| 23 | **ACS Email** | Azure Communication Services Email | HITL email channel (replaces WorkIQ) | Custom sender domain in private VNet; HTML body with deep-links to `hitl-webform` ACA app |
| 24 | Private MCP servers in ACA | Python (FastAPI + `mcp` lib) | `cosmos-mcp` (read+write), `content-understanding-mcp`, `acs-email-mcp`, `feature-flags-mcp` | All internal ingress; Managed Identity to backing services. |
| 25 | Key Vault | `kv-albaranes-prd` | Secrets, certs | RBAC mode, no access policies |
| 26 | Application Insights + Log Analytics | `ai-albaranes-prd` / `law-albaranes-prd` | Telemetry, GenAI traces | OTel exporter; correlation = `albaran_id` |
| 27 | Container Registry | `acralbaranesprd` Premium | Private images for agents/workers | Private endpoint; image scanning |
| 28 | Self-hosted GitHub runners | ACA Jobs (Brett) | Deploy into private VNet | Bootstrap pattern; only path that can `terraform apply` / `bicep deploy` |
| 29 | Azure Firewall **or** NAT Gateway | Egress control | Outbound to BC, OpenAI, ACS | Brett picks final design |
| 30 | Private DNS zones | `privatelink.*` for every PaaS | Internal name resolution | Linked to spoke VNet |

---

## 1.4 Hosting Model — Everything in ACA + Service Bus (D‑R‑019, rewritten)

The system has **one compute plane (Azure Container Apps)** and **one orchestration framework (MAF SDK in-process)**. Azure OpenAI is reached through the Foundry project as a **model + telemetry endpoint**. **No Durable Functions. No Foundry-hosted agents.** All long-running waits use **Service Bus scheduled messages** for timers and **Cosmos** for state.

| Component | Runs in | Technology | Why here |
|---|---|---|---|
| **All AI agents (A1–A6)** at MVP, **A7–A8** at steady state | **Azure Container Apps** | **Microsoft Agent Framework (MAF) SDK v1.0+ in Python 3.12, in-process** | Single runtime, single VNet integration, full HandOff support, no preview dependencies |
| **MAF orchestrator** (`SequentialBuilder` + `HandoffBuilder` for A1→A2→{A3→A4→A5}) | **Azure Container Apps** (`agentic-orchestrator` app) | MAF SDK orchestrations module | Orchestration is a Python class composing agents; runs wherever the agents run |
| **Flow 0 (dedup)** | **ACA Job** | Python, KEDA-scaled on Service Bus queue length | Pure adapter; no model calls |
| **HITL webhook receiver** | **Azure Container Apps** (`hitl-webform` app) | Python 3.12 + FastAPI | Receives ACS email button-click; publishes `hitl.response.*` |
| **HITL timers (24h reminder, 48h escalation, 72h hard cap)** | **Azure Service Bus** scheduled messages | `ScheduleMessageAsync(message, scheduledEnqueueTime)` | Native to Service Bus; survives restarts; cancellable when `hitl.response` arrives first; replaces every Durable Functions timer in ADR-v2 |
| **Long-running state** (HITL pending, in-flight albarán, supplier reputation) | **Cosmos DB NoSQL** | Documents in `albaranes`, `hitl_approvals`, `supplier_reputation` | State of record. Change Feed used only for read-models, never as a trigger |
| **Inter-agent / inter-flow eventing** | **Service Bus topic** `albaran-events` with subscriptions per state | Standard tier, DLQ on every subscription | Events drive everything: `albaran.recibido`, `.extraido`, `.discrepancia`, `.baja_confianza`, `.error_validacion`, `.error_inventario`, `.escalado`, `.inventariado`, `hitl.response.*` |
| **Model endpoints** | **Azure OpenAI** (via Foundry project) | `gpt-5.1` (multimodal), `gpt-5-mini` (text) | Model serving only. Foundry adds a managed control plane + tracing on top of Azure OpenAI |
| **Private MCP servers** (`cosmos-mcp`, `content-understanding-mcp`, `acs-email-mcp`, `feature-flags-mcp`) | **Azure Container Apps** | Python (FastAPI + `mcp` library) | Internal ingress; consumed by agents via `MCPStreamableHTTPTool` |
| **BC native MCP (read + write)** | **Business Central Online** | Microsoft-managed | OAuth2 Auth Code + PKCE, delegated identity |
| **GitHub self-hosted runners** | **ACA Jobs** | Container image with GH Actions runner agent | Only egress path that can deploy IaC into the private VNet (Brett owns) |

### How agents are deployed

Each agent is a **Python class instantiated inside an ACA container**, not a Foundry resource. Examples:

```python
# inside agentic-orchestrator container
from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.foundry import FoundryChatClient
from agent_framework.orchestrations import SequentialBuilder, HandoffBuilder
from azure.identity import ManagedIdentityCredential

cred = ManagedIdentityCredential()
gpt51 = FoundryChatClient(project_endpoint=AOAI_PROJECT, model="gpt-5.1", credential=cred)
gpt5mini = FoundryChatClient(project_endpoint=AOAI_PROJECT, model="gpt-5-mini", credential=cred)

content_understanding = MCPStreamableHTTPTool(name="cu", url=CU_MCP_URL)
bc_read = MCPStreamableHTTPTool(name="bc_read", url=BC_READ_MCP_URL)
bc_write = MCPStreamableHTTPTool(name="bc_write", url=BC_WRITE_MCP_URL)
cosmos = MCPStreamableHTTPTool(name="cosmos", url=COSMOS_MCP_URL)

extractor = Agent(client=gpt51, name="A1_Extractor",
                  instructions=load("a1_extractor.md"),
                  tools=[content_understanding])

triage = Agent(client=gpt5mini, name="A2_Triage",
               instructions=load("a2_triage.md"),  # strict JSON: {route, reasoning}
               tools=[cosmos],
               require_per_service_call_history_persistence=True)

coherence = Agent(client=gpt5mini, name="A3_Coherence",
                  instructions=load("a3_coherence.md"),
                  tools=[bc_read, cosmos],
                  require_per_service_call_history_persistence=True)

validator = Agent(client=gpt5mini, name="A4_Validator",
                  instructions=load("a4_validator.md"),
                  tools=[bc_read, cosmos],
                  require_per_service_call_history_persistence=True)

inventory = Agent(client=gpt5mini, name="A5_Inventory",
                  instructions=load("a5_inventory.md"),
                  tools=[bc_write, cosmos],  # @tool(approval_mode="always_require") on Post Purchase Receipt
                  require_per_service_call_history_persistence=True)

# Composition:
extraction_step = SequentialBuilder(participants=[extractor]).build()  # single-step seq for telemetry symmetry
routing = (HandoffBuilder(name="albaran_routing",
                          participants=[triage, coherence, validator, inventory])
           .with_start_agent(triage)
           .build())
```

The Service Bus message handler in the ACA app receives `albaran.recibido`, runs `extraction_step`, persists, then runs `routing` — both in the same Python process. HandOff is in-memory across agents A2–A5 within one albarán's run.

When A2/A3/A4 decide to bounce to HITL, they don't HandOff to A6; they **publish a Service Bus event** and the workflow run terminates cleanly. A6 picks up the event in a separate ACA app, sends the email, and waits (via Service Bus scheduled messages and the `hitl-webform` callback). On `hitl.response.aprobado_hitl`, a separate "resume" subscription on `agentic-orchestrator` reloads the albarán's Cosmos state and runs A5 only.

### Why no Durable Functions

ADR‑v2 used Durable Functions for: (a) state machine, (b) durable timers, (c) sub-orchestrator for HITL. All three are now provided by simpler primitives:

| Need | Was (ADR‑v2) | Now (ADR‑v3) |
|---|---|---|
| State machine | Durable orchestrator's in-memory state | Cosmos document `estado` field + Service Bus topic events + idempotent agent code |
| Durable timers (24h/48h/72h) | Durable Functions `CreateTimer` | **Service Bus `ScheduleMessageAsync`** — message enqueued for future delivery; cancellable via `CancelScheduledMessageAsync` |
| HITL sub-orchestrator | Durable Functions `CallSubOrchestrator` | A6 Communication Agent (event-driven, async) + `hitl-webform` callback + `hitl.response.*` events |
| Retries with backoff | Durable Functions `RetryOptions` | MAF agent retry policy + Service Bus delivery count + DLQ |
| Fan-out / fan-in | Durable Functions `Task.WhenAll` | Not needed in this pipeline; if it becomes needed, MAF `ConcurrentBuilder` covers it |

### Why no Foundry-hosted agents

Kiko's directive (2026‑05‑03 23:07): "all agents in MAF's ACA runtime, since we need HandOff for A2→A5." Foundry's prompt-agents API does not expose HandOff; HandOff is a MAF-SDK orchestration concern that runs in our process. Foundry remains valuable as the **model deployment + tracing** surface for Azure OpenAI; we keep `FoundryChatClient` as our chat-client implementation.

---

## 2. Flow Design (Updated for ACA + MAF in-process, 6 agents)

### 2.1 Flow 0 — Ingestion & Dedup

**Trigger:** `BlobCreated` event from Event Grid → Service Bus queue `extraccion-in`.
**Worker:** **ACA Job** (KEDA scaler on queue length).
**Steps:**
1. Receive Service Bus message containing `{blob_url, etag, tienda_id, content_type}`.
2. Stage‑1 dedup keyed on `blob_etag` (only stable identity at upload time). Cosmos lookup; if hit → write `estado = duplicado`, ack, stop.
3. Otherwise insert seed document `{albaran_id, blob_etag, tienda_id, estado: 'recibido', received_at}`.
4. Publish to Service Bus topic `albaran-events` with subject `albaran.recibido`.

**Why two‑stage dedup:** stage 2 (`supplier_id, albaran_number`) runs at the end of Flow 1 once those fields are extracted (catches double-scans of the same physical albarán).

### 2.2 Flow 1 + 2 — Agentic pipeline (A1 → A2 → A3 → A4 → A5)

**Trigger:** `albaran.recibido` topic subscription → **`agentic-orchestrator` ACA app** (KEDA-scaled).
**Runtime:** Single Python process per albarán; MAF SDK in-process; calls Azure OpenAI via `FoundryChatClient`.
**Composition:**
```python
extraction = SequentialBuilder(participants=[A1_extractor]).build()
routing    = (HandoffBuilder(participants=[A2_triage, A3_coherence, A4_validator, A5_inventory])
              .with_start_agent(A2_triage)
              .build())

async def handle_recibido(msg):
    ctx = load_cosmos(msg.albaran_id)
    if ctx.estado != "recibido":          # idempotency guard
        return
    # A1 — Extraction
    res1 = await extraction.run(input={"blob_sas_url": ctx.blob_sas_url,
                                       "albaran_id": ctx.albaran_id})
    persist_extraction(res1)              # estado ∈ {extraido | baja_confianza | error_extraccion}
    if ctx.estado == "error_extraccion":
        publish("albaran.error_extraccion", ctx); return

    # A2..A5 — HandOff
    res2 = await routing.run(input={"albaran_id": ctx.albaran_id})
    # Each agent in routing either: (a) hands off to next, (b) publishes a
    # "needs HITL" event and the workflow ends cleanly, or (c) reaches A5 success.
```

**Per-agent behavior:**

| Agent | Inputs | Outputs / next hop |
|---|---|---|
| **A1 Extractor** (GPT‑5.1) | `{blob_sas_url, albaran_id}` | Strict-JSON extraction → Cosmos. State: `extraido` / `baja_confianza` / `error_extraccion`. Then HandOff into routing graph (or publish error event). |
| **A2 Triage** (GPT‑5‑mini, structured output) | `albaran_id`, `confianza_global`, supplier reputation | Strict JSON `{route, reasoning}`. `route ∈ {fast_track, normal, hitl, hard_reject}` → HandOff to A3 (normal); publish `albaran.baja_confianza` (direct HITL); publish `albaran.error_extraccion` (hard reject after Content Safety hit); or HandOff direct to A5 (fast-track) |
| **A3 Coherence** (GPT‑5‑mini) | `albaran_id` | `{coherence_ok, reasons[]}`. If ok → HandOff to A4. If not → publish `albaran.error_validacion` (Communication agent picks it up with ops CC) |
| **A4 Validator** (GPT‑5‑mini) | `albaran_id` | `{decision, deltas[]}`. `coincide` → HandOff to A5. `discrepancia` → publish `albaran.discrepancia` (Communication agent picks it up; HITL flow) |
| **A5 Inventory** (GPT‑5‑mini) | `albaran_id` (post-validation or post-HITL-approval) | Calls `bc-mcp-write.post_purchase_receipt` (`@tool(approval_mode="always_require")` enforced by MAF + Cosmos approval table). On success: `estado=inventariado`, publish `albaran.inventariado`. On error: `estado=error_inventario`, retry with exponential backoff (3×), then publish `albaran.error_inventario` |

**Resume after HITL approval:** A separate Service Bus subscription `hitl-approved-resume` on the `agentic-orchestrator` app listens for `hitl.response.aprobado_hitl`, reloads Cosmos state, and runs **A5 only** (skipping A1–A4 since their outputs are already persisted).

**Prompt-injection defense (A1):**
- Fixed system prompt; OCR text is data, never instruction.
- Strict JSON schema (extraction only).
- Content Safety pre-scan; flagged albaranes → `error_extraccion`.

**PII redaction (post-A1):** transportista name + signature regions stripped before persisting OCR text outputs.

**SLA target:** ≤ 30 s P95 for the extraction-through-validation pipeline (re-baseline post-benchmark). HITL adds the human delay.

### 2.3 Flow 3 — Communication Agent (HITL + ops alerts)

**Hosting:** dedicated **`communication-agent` ACA app** running A6 (MAF `ChatAgent`, GPT‑5‑mini for tone-adjusted body text only).

**Subscriptions:**
- `albaran.discrepancia` → send HITL approval email to tienda's `responsable_principal`
- `albaran.baja_confianza` → same path; template emphasizes confidence reasons
- `albaran.error_validacion` → ops CC (coherence failure ≠ HITL approval)
- `albaran.error_inventario` → ops alert + HITL retry option
- `albaran.escalado` → escalation email to `escalacion_a`

**HITL email send sub-flow (A6):**
```
1. Look up tiendas/<tienda_id> → responsable_principal, backup, escalacion_a.
2. Generate ACS email (HTML body): albarán summary + discrepancy table + 3 deep-link buttons:
     ACCEPT  → https://hitl-webform/.../?action=accept&token=...
     REJECT  → https://hitl-webform/.../?action=reject&token=...
     MODIFY  → https://hitl-webform/.../?action=modify&token=...
   SAS link to PDF (7-day TTL, audit-logged).
3. Send via acs-email-mcp.
4. Schedule 3 Service Bus messages on a delay topic (NOT albaran-events):
     - +24h: subject="hitl.reminder",       albaran_id, recipients=[principal,backup]
     - +48h: subject="hitl.escalation",     albaran_id, recipients=[escalacion_a]
     - +72h: subject="hitl.hardcap",        albaran_id, action=ops_alert
5. Record scheduled message sequence numbers in hitl_approvals/<albaran_id> Cosmos doc.
6. Persist: { albaran_id, msg_id, scheduled_sequence_numbers, sent_at }
```

**On `hitl.response.*` callback (from `hitl-webform`):**
1. Mark `hitl_approvals/<albaran_id>` as resolved.
2. **Cancel** all pending scheduled messages via `CancelScheduledMessageAsync(seq_no)`.
3. Publish to `albaran-events` topic:
   - ACCEPT → `hitl.response.aprobado_hitl` (resumes A5)
   - REJECT → `hitl.response.rechazado` (terminal, no supplier notification at MVP)
   - MODIFY → patch Cosmos with corrected fields, publish `hitl.response.aprobado_hitl`

**On 24h/48h/72h scheduled message firing (no human response yet):**
- 24h: A6 sends reminder email to `principal + backup`.
- 48h: A6 sets `estado=pendiente_escalacion`, sends escalation email to `escalacion_a`.
- 72h: A6 sets `estado=escalado`, raises ops alert, terminal.

### 2.4 HITL Webform — `hitl-webform` ACA app

A FastAPI app receiving the button-click GET / form POST from ACS email links.
- Validates the deep-link token (HMAC-signed, 7-day TTL).
- Persists the human's decision (and corrected fields for MODIFY) to Cosmos.
- Publishes `hitl.response.{aprobado_hitl|rechazado|modificado}` to `albaran-events`.
- Renders confirmation page.

Internal ingress; reachable to humans via Front-Door / APIM with corporate identity (Entra ID conditional access). Brett owns the edge topology.

### 2.5 Reconciliation Agent (A7) — deferred to MVP+1

ACA Job, cron daily 02:00 + weekly Sunday. Compares last-N-days `albaranes` (Cosmos) vs BC Posted Purchase Receipts (`bc-mcp-read`). Output: anomaly bundle published as `ops.reconciliation.report` event → A6 sends ops digest email.

### 2.6 Learning Agent (A8) — deferred to MVP+2

ACA Job, cron weekly Monday. Aggregates supplier OCR confidence trends, common discrepancy types, HITL approval/reject ratios from Cosmos events. Writes `supplier_reputation/<supplier_id>` documents that **A2 Triage** then reads for smarter routing.

---

## 3. State Machine

```
                    ┌─────────────┐
                    │  recibido   │  (Flow 0 seed)
                    └──────┬──────┘
                           │
            ┌──────────────┼──────────────┬──────────────────┐
            ▼              ▼              ▼                  ▼
      ┌─────────┐  ┌──────────────┐  ┌───────────┐   ┌──────────────┐
      │duplicado│  │  extraido    │  │baja_conf  │   │error_extracc │
      └─────────┘  └──────┬───────┘  └─────┬─────┘   └──────┬───────┘
        (terminal)        │                │                │
                          ▼                ▼                ▼
                    ┌──────────────┐ (HITL-first path) ─────┘
                    │  validado*   │       │
                    │ (in-memory   │       ▼
                    │  state of    │  ┌──────────────────────────┐
                    │ Agent2 step) │  │      HITL pending        │
                    └──┬───────┬───┘  │  (subOrch waiting        │
                       │       │      │   on event/timer)         │
                       │       │      └──┬─────────┬────────┬────┘
                       │       │         │         │        │
                       │       │   ┌─────▼───┐ ┌───▼────┐ ┌─▼────────────────┐
                       │       │   │aprobado_│ │recha-  │ │pendiente_escal / │
                       │       │   │ hitl    │ │zado    │ │  escalado        │
                       │       │   └────┬────┘ └────────┘ └──────────────────┘
                       │       │        │         (terminal) (terminal at hard cap)
                       │       │        │
                       │       ▼        ▼
                       │  ┌──────────────────┐
                       │  │  discrepancia    │ ← Agent2 finds Δ > 2%
                       │  └────────┬─────────┘
                       │           │ (always → HITL above)
                       │           │
                       └─────┬─────┘
                             ▼
                    ┌────────────────────┐
                    │   (call Agent 3)   │
                    └────────┬───────────┘
                             │
                  ┌──────────┴──────────┐
                  ▼                     ▼
          ┌──────────────┐      ┌──────────────────┐
          │ inventariado │      │ error_inventario │ → retry → HITL
          └──────────────┘      └──────────────────┘
            (terminal happy)      (transient, then terminal)

              Plus: cancelado_supervisor (manual ops kill from any non-terminal state)
```

**13 canonical states:**
`recibido`, `extraido`, `baja_confianza`, `error_extraccion`, `duplicado`, `discrepancia`, `error_validacion`, `aprobado_hitl`, `rechazado`, `pendiente_escalacion`, `escalado`, `inventariado`, `error_inventario`, `cancelado_supervisor` (14 if you count cancel — see §11 D‑R‑005).

**Tolerance:** **2 % global, applied to both quantity and price line‑level deltas.** Any line where `|delta| / expected > 0.02` → discrepancia. Aggregates (header total) checked at the same threshold.

---

## 4. LLM Strategy

| Agent | Model | Why | Cost notes |
|---|---|---|---|
| Agent 1 (Extraction) | **GPT‑5.1** (multimodal, flagship) | Heterogeneous albaranes, image+text reasoning, strict JSON schema fidelity | Most expensive — minimize prompt size, cache system prompt, use prompt caching where supported |
| Agent 2 (Triage) | **GPT‑5‑mini** | Lightweight routing with strict JSON structured output over policy context; handles edge cases without hard-coding every branch | Cheap enough to run on every albarán; structured output keeps downstream routing deterministic |
| Agent 3 (Coherence) | **GPT‑5‑mini** | Sanity checks against BC master data and extracted document context; flagship is overkill | ~5–10× cheaper than 5.1; reasoning depth is sufficient for this gate |
| Agent 4 (Validator) | **GPT‑5‑mini** | Pure structured comparison + reasoning over BC PO vs extraction | Should dominate token volume and stay cheap |
| Agent 5 (Inventory) | **GPT‑5‑mini** | Largely deterministic mapping to BC entities; LLM is convenience for natural-language tool selection | Could degrade to rule-based later if cost/risk warrant |

**Operational rules:**
- **Pin model versions** in Bicep (`gpt-5.1-2026-04-XX`, `gpt-5-mini-2026-04-XX`); never deploy `latest`.
- **Disable parallel tool calls** for strict‑schema extraction (Bishop, D‑BISHOP‑004).
- **Quarterly model‑refresh cadence** in operational runbook — owned by Ripley.
- **No cost ceiling at MVP** (Kiko's directive). Budget alerts and per‑agent cost dashboards are mandatory; review monthly.
- **Token budget logging** per `albaran_id` propagated as App Insights custom dimensions.

---

## 5. MCP Strategy

**Native first, custom only where necessary** (Newt's principle).

| MCP server | Type | Operations | Notes |
|---|---|---|---|
| `bc-mcp-read` | **Native BC MCP** | Purchase Orders, PO Lines, Vendors, Items, Posted Purchase Receipts | OAuth2 Auth Code + PKCE, delegated identity. Tenant `562029ef-…`, env Production, company CRONUS USA Inc. |
| `bc-mcp-write` | **Native BC MCP** (separate config, scoped) | Post Purchase Receipt **only** | **No DELETE.** Custom AL bound action only if Burke's analysis shows Warehouse Receipt is needed (Q9) |
| `azure-blob-mcp` | **Native Azure MCP** | List, read PDFs by SAS | Avoid binary download via MCP unless required |
| `cosmos-mcp` | **Custom (thin)** | Read + write state transitions, HITL approval state, supplier reputation | Native Azure Cosmos MCP is read‑oriented today; we need write |
| `content-understanding-mcp` | **Custom wrapper** | Schema‑prompt OCR | No native MCP exists |
| `acs-email-mcp` | **Custom adapter** | Send HTML email via Azure Communication Services | Replaces WorkIQ. Used by A6 Communication agent. |
| `feature-flags-mcp` | **Custom (thin)** | Read Triage routing policy + per-supplier overrides | Read-only; backed by Cosmos `triage_policy` container |

**Security posture:**
- BC MCP: delegated user identity (audit who actually approved/posted).
- All Azure MCPs: Managed Identity + RBAC, no shared keys.
- All MCP tool inputs validated against JSON schema **before** agent invocation (defense in depth — agents do not have direct access to anything they can't be schema‑checked on).

---

## 6. Data Architecture

### 6.1 Cosmos DB

- **Account:** `cosmos-albaranes-prd`, NoSQL API, single‑region write (Sweden Central). DR: TBD post‑MVP.
- **Container `albaranes`** — aggregate root document.
  - **Partition key:** `/pk = ${tienda_id}_${yyyy_mm}` (synthetic, balanced + time‑based archival).
  - **Document shape (sketch):**
    ```json
    {
      "id": "<albaran_id guid>",
      "pk": "tienda_007_2026_05",
      "tienda_id": "tienda_007",
      "blob_etag": "0x8DC...",
      "blob_path": "albaranes-raw/2026/05/tienda_007/2026-05-04T08-12-33Z_a17.pdf",
      "supplier_id": "S00123",
      "numero_albaran": "A-2026-001234",
      "ref_pedido_bc": "PO-9001234",
      "fecha": "2026-05-04",
      "estado": "inventariado",
      "events": [
        { "ts": "...", "from": "recibido", "to": "extraido", "by": "agent1" },
        { "ts": "...", "from": "extraido", "to": "discrepancia", "by": "agent2", "deltas": [...] },
        ...
      ],
      "extracted": { "lineas": [...], "totales": {...}, "confianza_global": 0.92 },
      "hitl": { "user_upn": "...", "decision": "aprobado_hitl", "ip": "...", "ts": "...", "email_msg_id": "..." },
      "bc": { "posted_receipt_id": "PR-..." },
      "audit": { "trace_id": "<albaran_id>", "version": 7 }
    }
    ```
- **Container `tiendas`** — config (responsable_principal, backup, escalacion_a, store metadata). Partition key `/tienda_id`.
- **Container `dlq`** — poison messages from any flow, with full replay payload.
- **Change Feed:** **read‑models only** (analytics/reporting). NOT used as a state‑transition trigger.

### 6.2 Blob Storage

- **Containers:**
  - `albaranes-raw/yyyy/mm/tienda_id/` — original PDFs (immutable policy, **6 years retention**, AEAT alignment).
  - `albaranes-processed/yyyy/mm/` — derived artifacts (redacted images, OCR JSON dumps).
  - `dlq/` — failed payloads.
- **Access:** Private Endpoint only. SAS tokens for HITL email links, max 7‑day TTL, audit‑logged.
- **Immutability:** time‑based retention policy (legal hold) on `albaranes-raw`.

---

## 7. Networking — Private VNet (Brett owns final design)

**Confirmed requirements:**
- All Azure resources in a **single VNet in Sweden Central** with private endpoints.
- **No public endpoints** on data‑plane services.
- **Self‑hosted GitHub Actions runners** in ACA Jobs are the only deployment path into private resources (bootstrap pattern).
- Egress through **NAT Gateway or Azure Firewall** (Brett to choose; firewall preferred for BC + OpenAI traffic logging).

**Subnetting (proposed; Brett to validate):**
- `snet-aca-env` (Container Apps environment — agentic-orchestrator, communication-agent, hitl-webform, MCP servers, /23)
- `snet-aca-jobs` (ACA Jobs — Flow 0 dedup, Reconciliation A7, Learning A8, /27)
- `snet-pe` (Private Endpoints, /24)
- `snet-runners` (self‑hosted GitHub runners ACA, /27)
- `snet-egress` (Firewall/NAT, /26)
- `snet-bastion` (optional, ops jump access, /27)

**Private Endpoints required for:** Storage (Blob, Table), Cosmos, Service Bus, Key Vault, Container Registry, Application Insights ingestion, Foundry / Azure OpenAI, Container Apps environment ingress (internal), Event Grid (when GA), Azure Communication Services (when private-link GA — see O‑16), BC connection (Private Link if available, otherwise Firewall + URL allow‑list).

**Bootstrap (chicken‑and‑egg):**
1. Initial deployment: temporary public access on storage / Cosmos / KV from a fixed runner IP allow‑list, deploy network + ACA runners.
2. Lock down: remove public access, switch to runners‑only.
3. Steady state: every IaC change goes through self‑hosted runners.

**This is Brett's domain. Architecture says "must be private VNet"; Brett delivers the topology.**

---

## 8. Observability

- **OpenTelemetry GenAI semantic conventions** for all agent calls. Exporter: Azure Monitor OpenTelemetry Distro for Python.
- **Correlation:** `albaran_id` is the OTel `trace_id` from Flow 0 onward.
- **Application Insights workspaces:** per environment.
- **Custom dimensions on every span:** `albaran_id, tienda_id, supplier_id, agent_name, model, tokens_in, tokens_out, cost_estimate_usd`.
- **Key business metrics (dashboard, refreshed 5 min):**
  - Albaranes/day by `estado`
  - HITL response time P50/P95
  - Discrepancy rate (overall + per supplier)
  - Confidence distribution (Agent 1 confianza_global histogram)
  - LLM token spend / day / agent
  - Time‑to‑inventario P50/P95
  - State‑machine error rate (`error_extraccion`, `error_inventario`)
- **Alerts (P1):** error rate > 5 % over 15 min, queue length > 1000, BC MCP failures, HITL backlog > 50.

---

## 9. Security

- **Identity:** Managed Identities everywhere on the Azure side. No shared keys, ever.
- **BC:** OAuth 2.0 Authorization Code + PKCE, **delegated user identity** (we want the audit trail to show *who* the system acted on behalf of when posting a receipt).
- **Key Vault** for any non‑MI secret (BC client secrets, ACS connection string if not using Managed Identity).
- **No DELETE** on any MCP server. Period.
- **Coherence validation** (Agent 2) — security baseline:
  - PO exists in BC → required
  - Supplier exists in BC → required
  - Albarán date within `[PO date, today + 7d]` → required
  - PO state in BC ∈ {Open, Released} → required
  - **No digital signature verification** on the PDF (per Q12 answer; risk accepted).
- **Prompt‑injection defense** (Agent 1):
  - Fixed system prompt; OCR text is treated as data, never as instruction.
  - Strict JSON schema on outputs.
  - Content Safety pre‑scan on OCR text.
  - Supplier‑reputation tracking (start tracking; act on it later).
- **PII redaction:** transportista names + signature regions stripped before persisting OCR text outputs. Original PDF retained in encrypted Blob with restricted SAS.
- **Network:** §7.
- **GDPR:** Sweden Central is in‑EU, GDPR compliant. 6‑year retention aligned with Spanish AEAT. DPIA: Call to schedule.

---

## 10. Scaling

**Confirmed loads:**
- 25 stores
- ~200 suppliers
- Peak: **20–30 albaranes/store/day → ~750/day peak total**
- Distribution: bursty in mornings (deliveries arrive 06:00–11:00 local)

**Sizing implications (per environment):**

| Resource | Sizing |
|---|---|
| Service Bus | Standard (premium not needed at 750/day; **scheduled messages supported on Standard** — confirm 72h TTL holds, see O‑13) |
| Container Apps env | Workload profile: Consumption (default) + 1 Dedicated D4 profile for `agentic-orchestrator` (multimodal A1 bursts) |
| `agentic-orchestrator` ACA app | Min replicas 1, max 20, KEDA on `albaran.recibido` subscription depth, target msgs/replica = 5 |
| `communication-agent` ACA app | Min replicas 1, max 5, KEDA on multi-subscription depth (sum of HITL-related subjects + scheduled-message subjects) |
| `hitl-webform` ACA app | Min replicas 1, max 3 (HTTP scaler) |
| ACA Jobs (Flow 0, A7, A8) | Min 0, max 10, KEDA on queue / cron |
| Cosmos | Autoscale 1000–10000 RU/s on `albaranes` (revisit after benchmark; can tune lower) |
| Blob | Standard ZRS sufficient |
| Foundry / Azure OpenAI | Provisioned vs PAYG: **PAYG at MVP** (small, bursty); revisit at 2× volume |

**Burst headroom:** the architecture handles 5× peak (~3750/day) without re‑sizing — KEDA + Cosmos autoscale + Service Bus throughput absorb the spike. Beyond that, switch to provisioned OpenAI throughput units and Service Bus Premium.

---

## 11. Decisions Log

All decisions take ID `D‑R‑NNN` (Ripley‑led; team‑accepted unless noted).

| ID | Decision | Status | Rationale |
|---|---|---|---|
| **D‑R‑001** | LLMs: GPT‑5.1 (Agent 1), GPT‑5‑mini (Agents 2 & 3) | ✅ Accepted (Kiko) | Lifecycle (GPT‑4 retiring 2026); cost discipline |
| **D‑R‑002** | OCR: Content Understanding primary, DI v4.0 fallback. Final lock after Sprint 0 benchmark | ⏳ Provisional | Heterogeneous suppliers + grounded outputs |
| **D‑R‑003** | Inter‑flow eventing: **Service Bus topic + Cosmos for state**. Cosmos = data‑of‑record only, **not** a trigger. **No Durable Functions.** | ✅ Accepted (Kiko 2026‑05‑03 23:07/23:10) | Single compute plane (ACA); homogeneous ops; Change Feed coalesces intermediate states. Timers use Service Bus scheduled messages |
| **D‑R‑004** | HITL channel: **Azure Communication Services Email + ACA-hosted web form** | ✅ Accepted (Kiko 2026‑05‑03 22:45) | Full Python control, private VNet compatible, no external license/dependency. Replaces WorkIQ/Power Automate/Teams options. |
| **D‑R‑005** | State machine: 13 canonical states (+1 ops `cancelado_supervisor`) | ✅ Accepted | Closes PRD §4.6 gaps |
| **D‑R‑006** | Idempotency: two‑stage. Stage 1 = `blob_etag` at Flow 0; stage 2 = `(supplier_id, albaran_number)` at Flow 1 close | ✅ Accepted | Catches re‑uploads cheaply, double‑scans correctly |
| **D‑R‑007** | Cosmos partition key `/pk = tienda_id_yyyymm` | ✅ Accepted | Avoids hot/cold partitions across 25 stores |
| **D‑R‑008** | Region: **Sweden Central**, single primary | ✅ Accepted (Kiko) | Latency, sovereignty, AI capacity, GDPR |
| **D‑R‑009** | Tolerance: **2 % global** (qty + price, line‑level) | ✅ Accepted (Kiko) | Operational simplicity; per‑supplier deferred |
| **D‑R‑010** | Canonical albarán identity: **albarán number + supplier_id**; multiple albaranes per PO allowed | ✅ Accepted (Kiko) | Partial deliveries are real |
| **D‑R‑011** | Security: coherence validation (PO, supplier, dates) — **no digital signature verification** | ✅ Accepted (Kiko) | Risk accepted at MVP |
| **D‑R‑012** | All infrastructure inside private VNet; self‑hosted GH runners (ACA) for CI/CD | ✅ Accepted (Kiko) | Brett owns topology |
| **D‑R‑013** | MCP: Native BC MCP (read + scoped write). Custom MCPs only for Cosmos read+write, Content Understanding, ACS Email, Feature Flags | ✅ Accepted | Newt's "build less" recommendation |
| **D‑R‑014** | No DELETE on any MCP server | ✅ Accepted | Belt + suspenders against agent misbehavior |
| **D‑R‑015** | Pin LLM model versions in IaC; quarterly refresh cadence | ✅ Accepted | No `latest`, ever |
| **D‑R‑016** | Image retention: 6 years on `albaranes-raw` (immutable policy) | ✅ Accepted | AEAT alignment |
| **D‑R‑017** | Cost: no LLM ceiling at MVP; budget alerts mandatory; monthly review | ✅ Accepted (Kiko) | Visibility before cap |
| **D‑R‑018** | BC integration uses **standard MCP entities only** (Posted Purchase Receipt as success artifact). Custom AL only if Burke later proves Warehouse Receipt necessary | ⏳ Provisional | Risk accepted; Burke owns escalation |
| **D‑R‑019** | **Hosting model: ALL agents (A1–A6, plus deferred A7–A8) run in Azure Container Apps with the MAF SDK in‑process. No Foundry-hosted agents. No Durable Functions. Foundry = model + telemetry endpoint over Azure OpenAI. Timers = Service Bus scheduled messages. State = Cosmos.** | ✅ Accepted (Kiko 2026‑05‑03 23:07/23:10) | Single compute plane; full HandOff support (only available with MAF SDK in-process); homogeneous VNet integration; no preview-feature dependency; eliminates the ADR-v2 Foundry-vs-ACA-vs-Functions ambiguity. |
| **D‑R‑020** | **Agent roster: 6 agents at MVP (A1 Extractor, A2 Triage, A3 Coherence, A4 Validator, A5 Inventory, A6 Communication) + 2 deferred (A7 Reconciliation MVP+1, A8 Learning MVP+2). The PRD's 3-agent design is rejected.** | ✅ Accepted (Ripley, post Kiko challenge) | See `prerequisites/analysis/ripley-agentic-redesign.md`. Splits decisions out of the orchestrator (Triage), separates fraud/sanity from line-Δ comparison (Coherence vs Validator), and treats outbound communication as a first-class agent. Truly agentic vs functional pipeline. |
| **D‑R‑021** | **Triage Agent (A2) uses GPT‑5‑mini with strict JSON structured output schema (`{route: fast_track\|normal\|hitl\|hard_reject, reasoning: string}`); rules are provided as system-prompt context and the LLM reasons about edge cases.** | ✅ Accepted | Keeps routing policy explicit while handling ambiguous cases consistently; structured output preserves auditability and deterministic downstream branching. |
| **D‑R‑022** | **Coherence Agent (A3) split from Validator (A4).** A3 = world sanity (PO/supplier/dates/totals envelope); A4 = line-level Δ vs PO at 2% | ✅ Accepted | Different MCP scopes, different failure modes (ops vs HITL), different prompts. Coherence failures CC ops; line discrepancies do not. |
| **D‑R‑023** | **Communication Agent (A6) is event-driven on Service Bus, not a HandOff target.** It runs in a separate ACA app and resumes the main orchestration via published events. | ✅ Accepted | HITL is hours/days asynchronous; HandOff is in-memory synchronous within a workflow run. State lives in Cosmos throughout. |
| **D‑R‑024** | **HITL timers (24h reminder, 48h escalation, 72h hard cap) implemented via Service Bus scheduled messages** with cancellation on early `hitl.response.*` | ✅ Accepted | Replaces Durable Functions timers from ADR-v2. Native to Service Bus; cancellable via `CancelScheduledMessageAsync`. |
| **D‑R‑025** | **Reconciliation (A7) deferred to MVP+1; Learning (A8) deferred to MVP+2** | ✅ Accepted | Neither is on the critical path; A8 requires ≥4 weeks of data to be valuable. Closes the agentic loop once shipped (A8 → Cosmos `supplier_reputation` → A2 routing). |

---

## 12. Open Items

| # | Item | Owner | Decision needed by |
|---|---|---|---|
| O‑1 | **ACS Email feasibility for HITL** — sender domain provisioning in private VNet, deep-link signing/auth, callback edge (Front-Door + APIM in front of `hitl-webform`). Volume ~750/day, HITL rate 1–5% ≈ 8–40/day. | Newt | End of Sprint 0 |
| O‑2 | **Self‑hosted GitHub runners on ACA — bootstrap pattern viability** in Sweden Central. Image base, scaling model, secret provisioning to runners | Brett | End of Sprint 0 |
| O‑3 | **Azure AI Content Understanding GA timeline** in Sweden Central + benchmark vs DI v4.0 on ≥50 representative albaranes from ≥5 suppliers | Ash | Sprint 0 close |
| O‑4 | **BC custom AL audit** — even though Kiko states "BC standard, no custom extensions," Burke must spot‑check Warehouse Receipt and Item Journal during Sprint 0 | Burke | Sprint 0 close |
| O‑5 | **Azure OpenAI / Foundry private networking GA in Sweden Central** — confirm at deploy time. Fallback: Foundry through public-with-IP-allow-list while keeping all agents private. | Ripley + Brett | Sprint 0 close |
| O‑6 | **Approver routing** for the 25 stores: who is `responsable_principal` / `backup` / `escalacion_a` per tienda? | Lambert (config owner) | Before Sprint 2 |
| O‑7 | **Reject path** — does the supplier get notified? Out‑of‑scope at MVP per Q14, but flag for stakeholder confirmation | Kiko | Before Sprint 2 |
| O‑8 | **DR / second region** — currently single Sweden Central. Decide DR posture | Ripley + Dallas | Post‑MVP |
| O‑9 | **MAF v1.0 PoC in ACA** — verify `SequentialBuilder` + `HandoffBuilder` patterns end-to-end with 3 stub agents in a single ACA process before Sprint 1 lock | Ash | Sprint 0 close |
| O‑10 | (closed — superseded by D‑R‑004 ACS Email decision) | — | — |
| O‑11 | **Triage rule-set v1** — concrete thresholds for fast-track / normal / straight-to-HITL / hard-reject. Requires Lambert's input on Verdecora's risk tolerance | Ripley + Lambert | Sprint 1 |
| O‑12 | **Email-template inventory** — every outbound type (HITL initial, 24h reminder, 48h escalation, 72h hard-cap, ops drift digest, future supplier reject) owned in `infra/templates/` | Newt + Lambert | Sprint 1 |
| O‑13 | **Service Bus scheduled message TTL** — confirm 72h scheduled-enqueue holds on Standard tier (default topic message TTL is 14d, should be fine, verify) | Brett | Sprint 0 close |
| O‑14 | **MAF HandOff persistence in private VNet** — `require_per_service_call_history_persistence=True` requires somewhere to persist. Confirm in-memory (acceptable for single workflow run) vs Cosmos backing | Ash | Sprint 0 close |
| O‑15 | **A7 Reconciliation cron mechanism** — KEDA cron scaler vs ACA Jobs `scheduleTriggerConfig` | Brett | MVP+1 planning |
| O‑16 | **ACS Email private-link / NSP** — Network Security Perimeter setup is preview per Newt's analysis. Decide at deploy time whether to use VPN-only edge for `hitl-webform` or accept ACS-managed connectivity | Brett + Newt | Sprint 0 close |

---

## References

- `prerequisites/pliego-tecnico-albaranes.html` (PRD v1.0, Mayo 2026) — superseded by this document where they conflict.
- `prerequisites/analysis/ripley-requirements-analysis.md` — full architectural re‑evaluation, risk register, Q1–Q12.
- **`prerequisites/analysis/ripley-agentic-redesign.md` — 3→6 agent justification (D‑R‑020).**
- `prerequisites/analysis/bishop-llm-evaluation.md` — model selection rationale and OCR strategy.
- `prerequisites/analysis/burke-bc-analysis.md` — BC entities and receiving model.
- `prerequisites/analysis/newt-mcp-analysis.md` — MCP server scope and posture.
- `prerequisites/analysis/newt-acs-email-hitl.md` — ACS Email feasibility for HITL.
- `prerequisites/analysis/brett-private-networking.md` — VNet topology + runners.
- `prerequisites/analysis/ash-maf-research.md` — MAF v1.0 patterns (`SequentialBuilder`, `HandoffBuilder`, `MCPStreamableHTTPTool`).
- `prerequisites/analysis/call-foundry-research.md` — Foundry / Azure OpenAI capabilities.
- `.squad/decisions.md` — squad‑level governance decisions.

---

*— Ripley, Lead Architect*
*This document is the authoritative architecture (v3, 2026‑05‑04). Changes require a new ADR entry under §11 and Kiko's sign‑off.*
