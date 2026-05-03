# Architecture Decision Record — Sistema Inteligente de Gestión de Albaranes

> **Status:** v2 — Definitive (replaces PRD §3, §4, §10 architecture sections)
> **Author:** Ripley (Lead Architect)
> **Date:** 2026-05-04
> **Project:** Verdecora — Albaranes ingestion, validation, and BC inventory automation
> **Stack:** Python 3.12, Microsoft Agent Framework v1.0+, Azure AI Foundry, Azure Container Apps, Cosmos DB NoSQL, Service Bus, Durable Functions, Business Central Online (MCP-enabled)
> **Region:** **Sweden Central** (single primary region; DR design TBD post‑MVP)

This document supersedes the PRD's architecture sections and is the single source of architectural truth going forward. It incorporates all answers to Q1–Q12 and the new private‑networking + WorkIQ requirements communicated by Kiko on 2026‑05‑04. References to detailed analyses live in `prerequisites/analysis/` (Ripley, Bishop, Burke, Newt, Ash, Call).

---

## 1. Architecture Overview

### 1.1 Context (one paragraph)

Verdecora's in‑store capture app already exists and produces a PDF of each albarán that lands in Azure Blob Storage. The PDF carries the BC purchase‑order number on every albarán (no fuzzy matching). Our system picks up from that Blob event, extracts structured data with an AI agent, validates it against the BC purchase order with a 2 % global tolerance, sends discrepancies to a human via **email (WorkIQ)**, and on approval posts the receipt to Business Central via the **native BC MCP server**. All infrastructure is deployed inside a **private VNet in Sweden Central**, with self‑hosted GitHub runners (in ACA) as the only egress path into private resources.

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
│  ┌────────────────────────── Flow 0: Ingestion & Dedup ───────────────────────┐   │
│  │  Blob Storage (albaranes-raw/yyyy/mm/tienda_id/) ──┐                       │   │
│  │       │                                             ▼                       │   │
│  │       │                                   Event Grid (BlobCreated)          │   │
│  │       │                                             │                       │   │
│  │       │                                             ▼                       │   │
│  │       │                              Service Bus queue: extraccion-in       │   │
│  │       │                                             │                       │   │
│  │       │                                             ▼                       │   │
│  │       │                       Container Apps Job (KEDA-scaled)              │   │
│  │       │                       └─ Dedup check: hash(blob_etag, supplier,     │   │
│  │       │                          albaran_number) vs Cosmos                  │   │
│  │       │                          → if dup → estado=duplicado, stop          │   │
│  │       │                          → else → estado=recibido, enqueue Flow 1   │   │
│  │       │                                                                    │   │
│  └───────┼────────────────────────────────────────────────────────────────────┘   │
│          │                                                                         │
│  ┌───────┼─────────── Flow 1: Extraction (Agent 1) ─────────────────────────┐    │
│  │       ▼                                                                  │    │
│  │  Container Apps (MAF runtime)  →  Agent 1                                │    │
│  │     │  ├─ Tool: Azure AI Content Understanding (primary OCR)             │    │
│  │     │  │   └─ fallback: Document Intelligence v4.0 (selective)            │    │
│  │     │  ├─ LLM: GPT-5.1 (multimodal, structured outputs)                  │    │
│  │     │  ├─ Content Safety scan (prompt-injection defense)                 │    │
│  │     │  └─ PII redaction (transportista, firma)                           │    │
│  │     ▼                                                                    │    │
│  │  Cosmos DB write: albaranes/<albaran_id>                                 │    │
│  │     estado ∈ { extraido | baja_confianza | error_extraccion }            │    │
│  │     ▼                                                                    │    │
│  │  Service Bus topic: albaran.extraido                                     │    │
│  └─────┬────────────────────────────────────────────────────────────────────┘    │
│        │                                                                         │
│  ┌─────┼─── Flow 2: Validation + Inventory (Agents 2 & 3, Durable Functions) ─┐ │
│  │     ▼                                                                       │ │
│  │  Durable Functions Orchestrator (state machine owner)                       │ │
│  │     │                                                                       │ │
│  │     ├─ Activity: Agent 2 (GPT-5-mini)                                       │ │
│  │     │     ├─ MCP: BC native (read) — PO header, lines, vendor, items       │ │
│  │     │     ├─ MCP: Cosmos read — extracted JSON                              │ │
│  │     │     └─ Coherence checks (PO exists, supplier exists, dates coherent) │ │
│  │     │                                                                       │ │
│  │     ├─ Decision branch                                                      │ │
│  │     │     • coincide (Δ ≤ 2%)  → Activity: Agent 3                          │ │
│  │     │     • discrepancia OR baja_confianza → Flow 2b (HITL email)           │ │
│  │     │                                                                       │ │
│  │     ├─ Activity: Agent 3 (GPT-5-mini, mostly deterministic)                 │ │
│  │     │     └─ MCP: BC native (write) — Posted Purchase Receipt               │ │
│  │     │                                                                       │ │
│  │     └─ Cosmos final write: estado = inventariado | error_inventario         │ │
│  │                                                                             │ │
│  └───────────────┬─────────────────────────────────────────────────────────────┘ │
│                  │                                                                │
│  ┌───────────────┼──── Flow 2b: HITL via Email (WorkIQ) ────────────────────┐   │
│  │  Durable timer: 24h reminder, 48h escalation                              │   │
│  │     │                                                                     │   │
│  │     ▼                                                                     │   │
│  │  WorkIQ → email to responsable_principal (per tienda config)              │   │
│  │     · Accept / Reject / Modify buttons (deep link to correction form)     │   │
│  │     ▼                                                                     │   │
│  │  Container App webhook ← WorkIQ callback                                  │   │
│  │     ▼                                                                     │   │
│  │  Raise event into Durable orchestrator → resume → Agent 3 (or rechazado) │   │
│  └───────────────────────────────────────────────────────────────────────────┘   │
│                                                                                    │
│  ┌───────────────────── Cross-cutting platform services ─────────────────────┐   │
│  │  Azure AI Foundry project (Agents 1‑3 hosted)                             │   │
│  │  Azure Key Vault (no shared keys; Managed Identity everywhere)            │   │
│  │  App Insights + Log Analytics (OTel GenAI conventions)                    │   │
│  │  Self-hosted GitHub runners (ACA Jobs) — only deployment path             │   │
│  │  Private Endpoints for: Blob, Cosmos, Service Bus, Key Vault, Foundry,    │   │
│  │                          Container Apps env, Functions, ACR               │   │
│  │  Egress: Azure Firewall or NAT Gateway (Brett owns)                       │   │
│  └───────────────────────────────────────────────────────────────────────────┘   │
│                                                                                    │
└──────────────────────────────┬─────────────────────────────────────────────────────┘
                               │ Private Link / VNet integration
                               ▼
                    Business Central Online (MCP enabled)
                    Tenant: 562029ef-9022-45a6-b255-40cd71ebb2ce
                    Env: Production · Company: CRONUS USA Inc.
```

### 1.3 Component table (replaces PRD §3.1)

| # | Component | Service / Tech | Purpose | Notes |
|---|---|---|---|---|
| 1 | Capture app | Pre‑existing (Verdecora) | Generates PDF, uploads to Blob | **Out of scope.** API contract: PDF + metadata `{tienda_id, captured_at, user_upn}` |
| 2 | Blob Storage | `albaraneststXXXX` (Standard ZRS, hierarchical NS) | Raw + processed PDFs | Container `albaranes-raw/yyyy/mm/tienda_id/` ; **6‑year retention (legal hold + immutable policy)** |
| 3 | Event Grid | System topic on Storage Account | `BlobCreated` notification | Filtered to `albaranes-raw/` prefix |
| 4 | Service Bus | Standard tier, namespace `sb-albaranes-prd` | `extraccion-in` queue + `albaran-events` topic | DLQ on every entity; sessions disabled (no ordering req) |
| 5 | Container Apps environment | Internal (VNet‑only) | Hosts Flow 0 worker, Flow 1 agent, HITL webhook | Workload profile: Consumption + Dedicated for agents |
| 6 | Azure Functions (Durable) | Premium / EP plan, VNet integrated | Flow 2 orchestrator + HITL durable timers | Python 3.12, Durable v2 |
| 7 | Azure AI Foundry project | `foundry-albaranes-prd` | Hosts agents 1‑3, MCP tool registry | Per‑env project (dev/stg/prd) |
| 8 | Agent 1 | MAF v1.0+ in Foundry | Extraction | LLM: **GPT-5.1**; tools: Content Understanding, DI fallback, Content Safety |
| 9 | Agent 2 | MAF v1.0+ in Foundry | Validation | LLM: **GPT-5-mini**; tools: BC MCP (read), Cosmos read |
| 10 | Agent 3 | MAF v1.0+ in Foundry | Inventory write | LLM: **GPT-5-mini**; tool: BC MCP (write, scoped) |
| 11 | Azure AI Content Understanding | Primary OCR | Heterogeneous albaranes | Decision pending Sprint 0 benchmark vs DI |
| 12 | Document Intelligence v4.0 | Fallback OCR | Stable suppliers + CU‑GA hedge | Deploy but do not light up by default |
| 13 | Cosmos DB NoSQL | `cosmos-albaranes-prd` | Aggregate store + read‑models | Container `albaranes`, partition key `/pk = tienda_id_yyyymm` |
| 14 | BC native MCP (read) | Business Central Online (Production / CRONUS USA Inc.) | PO + Vendor + Items + Posted Receipts read | OAuth2 Auth Code + PKCE, delegated identity |
| 15 | BC native MCP (write) | Same BC tenant, separate scoped config | Post Purchase Receipt only | **No DELETE.** Optional bound‑action AL extension for Warehouse Receipt (Burke) |
| 16 | WorkIQ | Email‑driven HITL | Approve / Reject / Modify | Newt validating feasibility — fallback: Power Automate Approvals |
| 17 | Key Vault | `kv-albaranes-prd` | Secrets, certs | RBAC mode, no access policies |
| 18 | Application Insights + Log Analytics | `ai-albaranes-prd` / `law-albaranes-prd` | Telemetry, GenAI traces | OTel exporter; correlation = `albaran_id` |
| 19 | Container Registry | `acralbaranesprd` Premium | Private images for agents/workers | Private endpoint; image scanning |
| 20 | Self-hosted GitHub runners | ACA Jobs (Brett) | Deploy into private VNet | Bootstrap pattern; only path that can `terraform apply` / `bicep deploy` |
| 21 | Azure Firewall **or** NAT Gateway | Egress control | Outbound to BC, OpenAI, M365 | Brett picks final design |
| 22 | Private DNS zones | `privatelink.*` for every PaaS | Internal name resolution | Linked to spoke VNet |

---

## 2. Flow Design (Updated)

### 2.1 Flow 0 — Ingestion & Dedup

**Trigger:** `BlobCreated` event from Event Grid.
**Worker:** Container Apps Job (KEDA scaler on `extraccion-in` Service Bus queue).
**Steps:**
1. Receive Service Bus message containing `{blob_url, etag, tienda_id, content_type}`.
2. Compute `dedup_key = sha256(supplier_id_unknown_yet || albaran_number_unknown_yet || blob_etag)` — **in Flow 0 we only have `blob_etag` and `tienda_id`, so dedup‑v1 keys on `blob_etag`**. The richer business‑key dedup (`supplier_id, albaran_number`) happens at the end of Flow 1 once those fields are extracted.
3. Cosmos lookup against `albaranes` container by `blob_etag`. If hit → write `estado = duplicado`, ack message, stop.
4. Otherwise insert seed document `{albaran_id: guid, blob_etag, tienda_id, estado: 'recibido', received_at}`.
5. Publish to Service Bus topic `albaran-events` with subject `albaran.recibido`. Flow 1 subscribes.

**Why two‑stage dedup:** the only stable identity at upload time is `blob_etag`; the business key is only known after extraction. Both are checked. Re‑uploads of the same scan are caught at stage 1 (cheap); double‑scans of the same physical albarán are caught at stage 2 (right).

### 2.2 Flow 1 — Extraction (Agent 1)

**Trigger:** `albaran.recibido` topic subscription → Container App (KEDA‑scaled).
**Agent runtime:** Azure AI Foundry Agent Service, **GPT‑5.1**, MAF v1.0+.
**Pipeline:**
1. **Idempotency guard** (defense in depth): re‑check Cosmos for the same `albaran_id` — if `estado != 'recibido'`, drop.
2. **OCR call:** Content Understanding with the schema for "albarán Verdecora". Capture `confianza_global` and per‑field confidences.
3. **Multimodal LLM pass (GPT‑5.1):** structured‑outputs (strict JSON schema) — fields: `numero_albaran, fecha, supplier_id, ref_pedido (PO), lineas[], totales, observaciones, transportista, firma_digital_present`.
4. **Prompt‑injection defense:**
   - Fixed system prompt; no dynamic concatenation of OCR text into instructions.
   - Strict JSON schema (extraction *only*; no free‑form actions).
   - Content Safety scan over OCR text before LLM call; flagged albaranes go to `error_extraccion` and HITL.
5. **PII redaction:** transportista name + signature stripped from any text persisted outside the raw PDF.
6. **State assignment** (in same Cosmos write):
   - `confianza_global ≥ 0.85` and no schema violations → `extraido`
   - `0.60 ≤ conf < 0.85` → `baja_confianza` (auto‑HITL)
   - `conf < 0.60` or schema violation → `error_extraccion`
7. **Publish:** `albaran.extraido` (or `.baja_confianza` / `.error_extraccion`) to topic. Flow 2 subscribes to all three.

**SLA target:** ≤ 30 s P95 (re‑baseline post‑benchmark).

### 2.3 Flow 2 — Validation + Inventory (Durable Functions orchestrator)

**Trigger:** `albaran.extraido` (or `.baja_confianza` / `.error_extraccion`) → Function (`OnAlbaranExtraido` starter) → starts orchestrator.

**Orchestrator (`AlbaranOrchestrator`):**
```
input: { albaran_id }
1. estado := load(albaran_id).estado
2. if estado in (baja_confianza, error_extraccion):
       call HITL_subOrchestrator     # Flow 2b
       wait for resolution event
3. call Activity: AGENT2_VALIDATE(albaran_id)
   → returns { decision: coincide | discrepancia, deltas[], coherence_ok }
4. if not coherence_ok:                     # PO missing, supplier missing, dates broken
       set estado = error_validacion → HITL
5. if decision == discrepancia:
       set estado = discrepancia → call HITL_subOrchestrator
       wait for resolution event
       if rechazado: set estado=rechazado, return
       if aprobado_hitl: continue
6. call Activity: AGENT3_INVENTORY(albaran_id)
   → returns { posted_receipt_id }
   on error: retry with exponential backoff (3x), then estado=error_inventario → HITL
7. set estado = inventariado, persist
```

**Why Durable Functions, not Cosmos Change Feed:**
- Built‑in durable timers (24 h / 48 h SLAs) — survive restarts.
- Native DLQ + retries.
- Explicit state machine, not implicit through document mutations.
- Cosmos remains the **read‑model + audit log**, never the trigger.
- Decision: see §11, D‑R‑003.

### 2.4 Flow 2b — HITL via Email (WorkIQ)

**Sub‑orchestrator `HITL_subOrchestrator`:**
```
1. Look up tiendas/<tienda_id> → responsable_principal, responsable_backup, escalacion_a
2. Call WorkIQ activity → send email with:
     - Albarán summary (PDF link via SAS, 7-day TTL, audit-logged)
     - Discrepancy table
     - Buttons: ACCEPT | REJECT | MODIFY (deep-link to Container App correction form)
3. Wait for external event "HITL_RESPONSE" or durable timer
     - 24h timer: send reminder via WorkIQ → responsable_principal + responsable_backup
     - 48h timer: estado=pendiente_escalacion → email escalacion_a; reset wait
     - 72h hard cap: estado=escalado, raise ops alert, stop
4. On HITL_RESPONSE:
     - ACCEPT  → estado=aprobado_hitl, return continue
     - REJECT  → estado=rechazado, return stop  (no supplier notification in MVP)
     - MODIFY  → patch Cosmos with corrected fields, estado=aprobado_hitl, continue
5. Persist audit record: { user_upn, decision, deltas, ip, timestamp, email_msg_id }
```

**WorkIQ feasibility:** Newt is researching in parallel. **Hard fallback** if WorkIQ proves insufficient: **Power Automate Approvals** (cloud flow, Teams Approvals action). Architecturally interchangeable — the Container App webhook surface stays identical; only the email‑sender activity changes. See §12 Open Items.

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
| Agent 2 (Validation) | **GPT‑5‑mini** | Pure structured comparison + reasoning over BC PO vs extraction; flagship is overkill | ~5–10× cheaper than 5.1; should dominate token volume and stay cheap |
| Agent 3 (Inventory) | **GPT‑5‑mini** | Largely deterministic mapping to BC entities; LLM is convenience for natural‑language tool selection | Could degrade to rule‑based later if cost/risk warrant |

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
| `cosmos-mcp` | **Custom (thin)** | Read + write state transitions | Native Azure Cosmos MCP is read‑oriented today; we need write |
| `content-understanding-mcp` | **Custom wrapper** | Schema‑prompt OCR | No native MCP exists |
| `workiq-mcp` (or fallback `power-automate-mcp`) | **Custom adapter** | Send approval email + receive callback | Newt confirms WorkIQ feasibility |

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
- `snet-aca-env` (Container Apps environment, /23 — agent runtime is dense)
- `snet-functions` (Durable Functions VNet integration, /27)
- `snet-pe` (Private Endpoints, /24)
- `snet-runners` (self‑hosted GitHub runners ACA, /27)
- `snet-egress` (Firewall/NAT, /26)
- `snet-bastion` (optional, ops jump access, /27)

**Private Endpoints required for:** Storage (Blob, Table), Cosmos, Service Bus, Key Vault, Container Registry, Application Insights ingestion, Foundry, Function App, Container Apps environment ingress (internal), Event Grid (when GA), BC connection (Private Link if available, otherwise Firewall + URL allow‑list).

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
- **Key Vault** for any non‑MI secret (BC client secrets, WorkIQ API key if applicable).
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
| Service Bus | Standard (premium not needed at 750/day) |
| Container Apps env | Workload profile: Consumption (default) + 1 Dedicated D4 profile for Agent 1 (multimodal LLM bursts) |
| Agent 1 (extraction) | Min replicas 1, max 20, KEDA on `extraccion-in` queue length, target queue/replica = 5 |
| Durable Functions | Premium EP1, autoscale up to 10 instances |
| Cosmos | Autoscale 1000–10000 RU/s on `albaranes` (revisit after benchmark; can tune lower) |
| Blob | Standard ZRS sufficient |
| Foundry / OpenAI | Provisioned vs PAYG: **PAYG at MVP** (small, bursty); revisit at 2× volume |

**Burst headroom:** the architecture handles 5× peak (~3750/day) without re‑sizing — KEDA + Durable Functions + Cosmos autoscale absorb the spike. Beyond that, switch to provisioned OpenAI throughput units.

---

## 11. Decisions Log

All decisions take ID `D‑R‑NNN` (Ripley‑led; team‑accepted unless noted).

| ID | Decision | Status | Rationale |
|---|---|---|---|
| **D‑R‑001** | LLMs: GPT‑5.1 (Agent 1), GPT‑5‑mini (Agents 2 & 3) | ✅ Accepted (Kiko) | Lifecycle (GPT‑4 retiring 2026); cost discipline |
| **D‑R‑002** | OCR: Content Understanding primary, DI v4.0 fallback. Final lock after Sprint 0 benchmark | ⏳ Provisional | Heterogeneous suppliers + grounded outputs |
| **D‑R‑003** | Inter‑flow eventing: Service Bus + Durable Functions. Cosmos = data‑of‑record only, **not** a trigger | ✅ Accepted | Change Feed coalesces intermediate states; durable timers needed for HITL SLAs |
| **D‑R‑004** | HITL channel: **Email via WorkIQ** (Kiko's directive) | ⏳ Provisional pending Newt's WorkIQ feasibility — fallback = Power Automate Approvals | Lighter than custom bot; auditable |
| **D‑R‑005** | State machine: 13 canonical states (+1 ops `cancelado_supervisor`) | ✅ Accepted | Closes PRD §4.6 gaps |
| **D‑R‑006** | Idempotency: two‑stage. Stage 1 = `blob_etag` at Flow 0; stage 2 = `(supplier_id, albaran_number)` at Flow 1 close | ✅ Accepted | Catches re‑uploads cheaply, double‑scans correctly |
| **D‑R‑007** | Cosmos partition key `/pk = tienda_id_yyyymm` | ✅ Accepted | Avoids hot/cold partitions across 25 stores |
| **D‑R‑008** | Region: **Sweden Central**, single primary | ✅ Accepted (Kiko) | Latency, sovereignty, AI capacity, GDPR |
| **D‑R‑009** | Tolerance: **2 % global** (qty + price, line‑level) | ✅ Accepted (Kiko) | Operational simplicity; per‑supplier deferred |
| **D‑R‑010** | Canonical albarán identity: **albarán number + supplier_id**; multiple albaranes per PO allowed | ✅ Accepted (Kiko) | Partial deliveries are real |
| **D‑R‑011** | Security: coherence validation (PO, supplier, dates) — **no digital signature verification** | ✅ Accepted (Kiko) | Risk accepted at MVP |
| **D‑R‑012** | All infrastructure inside private VNet; self‑hosted GH runners (ACA) for CI/CD | ✅ Accepted (Kiko) | Brett owns topology |
| **D‑R‑013** | MCP: Native BC MCP (read + scoped write). Custom MCPs only for Cosmos write, Content Understanding, WorkIQ | ✅ Accepted | Newt's "build less" recommendation |
| **D‑R‑014** | No DELETE on any MCP server | ✅ Accepted | Belt + suspenders against agent misbehavior |
| **D‑R‑015** | Pin LLM model versions in IaC; quarterly refresh cadence | ✅ Accepted | No `latest`, ever |
| **D‑R‑016** | Image retention: 6 years on `albaranes-raw` (immutable policy) | ✅ Accepted | AEAT alignment |
| **D‑R‑017** | Cost: no LLM ceiling at MVP; budget alerts mandatory; monthly review | ✅ Accepted (Kiko) | Visibility before cap |
| **D‑R‑018** | BC integration uses **standard MCP entities only** (Posted Purchase Receipt as success artifact). Custom AL only if Burke later proves Warehouse Receipt necessary | ⏳ Provisional | Risk accepted; Burke owns escalation |

---

## 12. Open Items

| # | Item | Owner | Decision needed by |
|---|---|---|---|
| O‑1 | **WorkIQ feasibility for HITL email** — does WorkIQ support outbound approval emails with deep‑link callbacks at the volume (~750/day, 1–5 % HITL rate ≈ 8–40/day)? Auth model? Webhook contract? | Newt | End of Sprint 0 |
| O‑2 | **Self‑hosted GitHub runners on ACA — bootstrap pattern viability** in Sweden Central. Image base, scaling model, secret provisioning to runners | Brett | End of Sprint 0 |
| O‑3 | **Azure AI Content Understanding GA timeline** in Sweden Central + benchmark vs DI v4.0 on ≥50 representative albaranes from ≥5 suppliers | Ash | Sprint 0 close |
| O‑4 | **BC custom AL audit** — even though Kiko states "BC standard, no custom extensions," Burke must spot‑check Warehouse Receipt and Item Journal during Sprint 0 (risk accepted, but verify) | Burke | Sprint 0 close |
| O‑5 | **Foundry Agent Service VNet injection GA in Sweden Central** — confirm. Fallback: host MAF agents directly in Container Apps | Ripley + Brett | Sprint 0 close |
| O‑6 | **Approver routing** for the 25 stores: who is `responsable_principal` / `backup` / `escalacion_a` per tienda? | Lambert (config owner) | Before Sprint 2 |
| O‑7 | **Reject path** — does the supplier get notified? Out‑of‑scope at MVP per Q14, but flag for stakeholder confirmation | Kiko | Before Sprint 2 |
| O‑8 | **DR / second region** — currently single Sweden Central. Decide DR posture (cross‑region replication of Cosmos + Blob, RTO/RPO target) | Ripley + Dallas | Post‑MVP |
| O‑9 | **MAF v1.0 PoC** — verify pseudocode patterns against actual Python SDK before Sprint 1 lock | Ash | Sprint 0 close |
| O‑10 | **Power Automate Approvals fallback** — keep ready as plug‑in replacement for WorkIQ (only the email‑sender activity changes) | Newt | Sprint 0 close |

---

## References

- `prerequisites/pliego-tecnico-albaranes.html` (PRD v1.0, Mayo 2026) — superseded by this document where they conflict.
- `prerequisites/analysis/ripley-requirements-analysis.md` — full architectural re‑evaluation, risk register, Q1–Q12.
- `prerequisites/analysis/bishop-llm-evaluation.md` — model selection rationale and OCR strategy.
- `prerequisites/analysis/burke-bc-analysis.md` — BC entities and receiving model.
- `prerequisites/analysis/newt-mcp-analysis.md` — MCP server scope and posture.
- `prerequisites/analysis/ash-maf-research.md` — MAF v1.0 patterns.
- `prerequisites/analysis/call-foundry-research.md` — Foundry Agent Service capabilities.
- `.squad/decisions.md` — squad‑level governance decisions.

---

*— Ripley, Lead Architect*
*This document is the authoritative architecture. Changes require a new ADR entry under §11 and Kiko's sign‑off.*
