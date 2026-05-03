# Squad Decisions

## Active Decisions

### 2026-05-03: Lenguaje de implementación — Python
**By:** Kiko de Angel
**What:** Todo el proyecto se implementa en Python, salvo la parte de IaC (Bicep). Esto incluye agentes IA, MCP servers custom (si los hubiera), webhooks, procesadores, y tests.
**Why:** Preferencia del usuario. Microsoft Agent Framework v1.0+ tiene SDK principal en Python.

### 2026-05-03: Metodología DevOps estricta
**By:** Kiko de Angel
**What:** Todo trabajo sigue el ciclo obligatorio: Issue → Branch → Dev → Test → Commit → Push → PR → Review → Merge → Close. Sin excepciones. Hicks (DevOps Lead) lo hace cumplir.
**Why:** Directiva del usuario para mantener trazabilidad y calidad en todo el ciclo de vida.

### 2026-05-03: MCP Servers custom — evaluar antes de implementar
**By:** Kiko de Angel
**What:** No dar por hecho que se necesitan MCP servers custom para Blob/Cosmos/DocIntel. El MCP nativo de Azure y BC puede cubrir muchas necesidades. Newt (MCP Analyst) debe evaluar qué se necesita realmente. Para Teams, considerar WorkIQ como alternativa.
**Why:** Simplificar la arquitectura evitando componentes innecesarios.

### 2026-05-03T22:30: Answers to blocking questions Q1-Q12 + new requirements
**By:** Kiko de Angel (via Copilot)
**What:**
- **Q1 (capture app):** EXISTS. Generates PDF, stores in Blob Storage. Not in scope.
- **Q2 (BC version):** Business Central Online. MCP enabled (config provided in session 1).
- **Q3 (PO matching):** Always has PO number on albarán. No fuzzy matching needed.
- **Q4 (HITL):** CHANGE — Use EMAIL instead of Teams. WorkIQ for sending emails with accept/reject/modify buttons. NO Teams bot.
- **Q5 (tolerances):** Global max 2% error tolerance. Not per-supplier.
- **Q6 (offline):** Stable internet. PDF from mobile phone. No offline buffering needed.
- **Q7 (volumes):** 25 stores, ~200 suppliers, peak 20-30 albaranes/store/day (~750/day peak total).
- **Q8 (compliance):** No special AEAT requirements. GDPR = use Sweden Central as Azure region. Nothing else.
- **Q9 (AL custom):** NOT ANSWERED — must follow up.
- **Q10 (LLM):** OK with GPT-5.1 / GPT-5-mini. No cost ceiling initially, will monitor.
- **Q11 (dedup):** Albaran number = canonical ID. Multiple albaranes per PO allowed (partial deliveries).
- **Q12 (security):** Validate coherence: PO number exists, supplier exists in BC, dates coherent. No digital signature verification.
**Why:** Unblocks Sprint 1 design.

### 2026-05-03: Private Networking and CI/CD Infrastructure
**By:** Kiko de Angel (from Q13-NEW)
**What:**
- ALL infrastructure in private VNet.
- Self-hosted GitHub runners in ACA for CI/CD deployments.
- Avoids chicken-and-egg problem with IaC deployment to private resources.
- Region: Sweden Central (GDPR requirement).
**Why:** Security and compliance requirement for GDPR.

### 2026-05-03T22:45: HITL Channel — ACS Email confirmed
**By:** Kiko de Angel (via Copilot)
**What:** HITL uses Azure Communication Services Email to send HTML emails with action buttons linking to a Container App web form. Accept/Reject/Modify flow handled by the web form + Cosmos DB + Durable Functions timers (24h reminder, 48h escalation). No Teams bot, no Power Automate, no Actionable Messages.
**Why:** Full Python control, Private VNet compatible, no external dependencies or licenses.

### 2026-05-03: PRD Pseudocode Corrections for MAF v1.0
**By:** Ash (MAF Specialist)
**Priority:** HIGH — blocks implementation planning
**What:**
- `McpToolProvider` → `MCPStreamableHTTPTool`: Requires actual URL, not server name.
- `HandoffWorkflow` → `HandoffBuilder`: Use `.with_start_agent(...).build()`. Routing is autonomous via agent instructions.
- `FoundryChatClient` constructor: Requires `(project_endpoint=..., model=..., credential=...)`.
- Import paths: `FoundryChatClient` lives in `agent_framework.foundry`, not top-level.
- All handoff agents must set `require_per_service_call_history_persistence=True`.
**Why:** PRD as-written uses classes/APIs that do not exist in MAF v1.0 GA.
**Action:** Update architecture docs to reflect actual MAF v1.0 API. See `prerequisites/analysis/ash-maf-research.md` for corrected code patterns.

### 2026-05-03: LLM Model Strategy
**By:** Bishop (LLM/OCR Specialist)
**What:**
- Use **GPT-5 family** as production baseline (instead of GPT-4o/GPT-4.1).
- Agent 1 (Extraction): `gpt-5-mini`.
- Agent 2 (Validation): `gpt-5.5`.
- Agent 3 (Inventory): `gpt-5-mini`.
- Keep **Azure AI Document Intelligence** as OCR foundation. Do NOT move to LLM-only OCR as baseline.
- Start with **Read/Layout** and add supplier-specific custom extraction only where real errors justify it.
- Replace unconditional "double pass" with **selective hybrid escalation**: Always run OCR first, only call multimodal LLM when confidence/rules indicate uncertainty or mismatch.
- Use **strict JSON Schema structured outputs** for all schema-critical agent steps.
- Treat **Claude in Foundry** as benchmark candidate, not production baseline, until preview risk is acceptable.
**Why:** GPT-4o/4.1/o3 have 2026 retirement horizons. GPT-5 family provides better lifecycle runway. Document Intelligence provides best production-grade OCR grounding. Selective hybrid design reduces cost while preserving accuracy.

### 2026-05-03: Business Central Entity and Receiving Model
**By:** Burke (BC/Dynamics Specialist)
**What:**
- Use native BC MCP only for standard read entities: POs, PO Lines, Vendors, Items, Posted Purchase Receipts.
- Do NOT assume Warehouse Receipt is native MCP entity. Plan for **custom AL API page/bound action** if needed.
- Do NOT treat General Journal Lines as Item Journal Lines. If needed, treat as **custom AL work**.
- Receiving flow must be **location-driven**, not globally warehouse-driven.
- Use **Posted Purchase Receipt** as canonical success artifact.
- Split MCP security: read-only config for validation, tightly scoped execution config for approved write path. Keep Delete disabled everywhere.
**Why:** Keeps architecture aligned with standard BC behavior instead of forcing every scenario through Warehouse Receipt or Item Journal. Avoids overestimating what native BC MCP exposes.
**Follow-up:** Confirm location setup. Decide whether receipt-only required or if custom AL endpoints allowed.

### 2026-05-03T23:07: Hosting model & no Durable Functions
**By:** Kiko de Angel (via Copilot)
**What:**
1. ALL agents (1, 2, 3) run in ACA with MAF SDK. No agents in Foundry.
2. MAF handles orchestration including HandOff between Agent 2 → Agent 3.
3. NO Durable Functions. Everything in ACA.
4. Azure AI Foundry = model endpoints + telemetry, NOT agent hosting.
5. MAF CAN orchestrate Foundry-hosted agents (non-HandOff), but since we need HandOff for Agent 2→3, all agents run in MAF's ACA runtime.
**Why:** Simplicity — single runtime (ACA), single orchestration framework (MAF), no split between hosting platforms. Kiko's directive.

### 2026-05-03T23:10: No Durable Functions, all ACA + Service Bus
**By:** Kiko de Angel (via Copilot)
**What:** No Durable Functions in the project. Everything runs on ACA + Service Bus. Timers for HITL (24h/48h) use Service Bus scheduled messages. State lives in Cosmos DB. This maximizes homogeneity: one compute platform, one deployment model, one VNet integration pattern.
**Why:** Kiko wants a homogeneous environment for simplified operations.

### 2026-05-03T23:31: A2A descartado, agentes in-process en MAF
**By:** Kiko de Angel (via Copilot)
**What:**
1. A2A is NOT an option — MAF Python agents cannot be exposed as A2A directly (not yet supported).
2. All agents run in-process in the same MAF runtime on ACA. Simple, no distributed agents.
3. No over-engineering. WorkflowBuilder orchestrates agents within the same process.
4. Future-proof: if scaling demands it, convert to hosted-agents. For now, keep them in the MAF runtime.
**Why:** Simplicity. A2A is not mature enough in MAF Python. In-process agents work fine for our volume (~750/day).

### 2026-05-03: Foundry Agent Service as Primary Platform
**By:** Call (Foundry Architect)
**What:** Treat **Azure AI Foundry Agent Service** as primary platform for agent lifecycle, identity, tracing, evaluation, publishing.
- **Foundry:** model endpoints + telemetry only.
- **Container Apps:** MAF SDK agents (all 6 at MVP), Event Grid and Change Feed adapters, webhook processors, private MCP servers.
- Prefer **in-process MAF agents** (WorkflowBuilder) for known deterministic pipelines.
- Require **Application Insights** from day one.
- Require **`allowed_tools`** and approval policies for MCP integrations.
**Why:** Service is GA at platform level for model endpoints. Container Apps + MAF is most stable production path for orchestrated agents at current MAF SDK maturity. Splits concern cleanly: Foundry = model+telemetry, ACA = compute+orchestration.

### 2026-05-03: DevOps Setup and Infrastructure
**By:** Hicks (DevOps Lead)
**Status:** Partial completion
**Completed:**
- Full project scaffolding: `src/`, `tests/`, `infra/`, `docs/`, `.github/workflows/`.
- CI/CD pipeline with Python 3.12+ matrix testing, linting (flake8), type checking (mypy), unit & integration tests, code coverage.
- Placeholder documentation.
**Blockers:**
- GitHub Labels: Cannot create due to pull-only access. Needs team member with admin access.
- Commands stored in `.squad/agents/hicks/history.md`.
**Enforcement:** All code changes follow strict DevOps cycle. No PRs merge without passing CI/CD pipeline.

### 2026-05-03: MCP Strategy and Architecture
**By:** Newt (MCP Analyst)
**What:**
- Reuse **native Business Central MCP server** instead of building separate custom BC MCP servers.
- Use **two BC configurations** (read-only and inventory-write) rather than two BC servers.
- **Blob Storage:** native Azure MCP exists; avoid bespoke blob MCP unless binary download through MCP proves necessary.
- **Cosmos DB:** plan for **write-capable adapter** unless state writes move outside MCP.
- **Document Intelligence:** plan **custom wrapper/integration**. No dedicated native Azure MCP found.
- **Teams/HITL:** WorkIQ is not a substitute for Teams Adaptive Cards. Use Teams-capable integration with thin adapter only if MCP invocation required.
- **Authentication:** BC MCP uses OAuth 2.0 + PKCE with delegated identity. Azure components use Managed Identity + RBAC.
**Why:** Build **less MCP infrastructure** than PRD implies. Keep BC native, keep Azure native where it works, custom-build only thin missing pieces.

### 2026-05-03: Ripley Requirements Analysis — Proposed Decisions
**By:** Ripley (Requirements Analyst)
**Status:** PROPOSED — pending team review

**D-RIPLEY-001: Target LLM models**
- Standardize on **GPT-5.1** (multimodal flagship) for Agent 1 (extraction).
- **GPT-5-mini** (or GPT-5.1-mini) for Agents 2 & 3.
- Explicitly forbid GPT-4o and GPT-4.1 in production.
- Rationale: GPT-4o/4.1 retiring during 2026. GPT-5.x has longer runway, native multimodal, better structured-output adherence.
- Pin versions in Bicep IaC. Quarterly refresh cadence.

**D-RIPLEY-002: Primary OCR/extraction service**
- Default to **Azure AI Content Understanding** as primary extraction service.
- Keep Azure AI Document Intelligence v4.0 prebuilt-invoice as fallback for stable suppliers.
- Rationale: Content Understanding outperforms DI on diverse layouts (~95% vs ~87% field-level accuracy on independent benchmarks).
- Owner: Ash, with Ripley sign-off on benchmark methodology.
- Selection contingent on Sprint 0 benchmark against ≥50 representative albaranes from ≥5 suppliers.

**D-RIPLEY-003: Inter-flow event bus and state orchestration**
- Replace "Cosmos DB Change Feed as inter-flow trigger" with **Service Bus topics + Durable Functions** orchestration.
- Cosmos DB becomes data-of-record only, not trigger.
- Event Grid → Service Bus queue → Container Apps Job for Flow 1.
- Service Bus topic → Durable Functions orchestrator for Flow 2 (validation + HITL + inventory).
- Rationale: Change Feed coalesces updates per logical key, risking silent loss of intermediate transitions. Durable Functions provides reliable timers (perfect for 24-48h HITL), DLQ, retries, compensation/saga semantics, explicit state machine.
- Trade-off: Adds Functions to platform. Fallback = event-sourced sibling Cosmos container if team prefers all-Container-Apps.

**D-RIPLEY-004: HITL channel**
- Default to **Power Automate Approvals** in Microsoft Teams for HITL decisions (accept/reject/correct).
- Small Container App web form for line-by-line corrections, linked from approval card.
- Custom Bot Framework bot is plan B only if Approvals proves insufficient.
- Rationale: Approvals provides native Teams integration, built-in reminders, escalation, audit trail, avoids tenant policy risk on custom bots.
- **UPDATE:** Overridden by Q4 answer — use **EMAIL via WorkIQ** instead.
- **Implementation strategy (Newt, 2026-05-03):**
  - MVP: Power Automate approval email + backend callback + small web form for `Modify`.
  - Advanced: Microsoft Graph `sendMail` + Outlook Actionable Message + HTTP endpoint.
  - WorkIQ role: context/intelligence only, not approval orchestration.
  - Modify: handled via web form or limited structured inputs, not in-email wizard.
  - Escalation/reminder: Power Automate or orchestrator, not WorkIQ.

**D-RIPLEY-005: Albarán state machine (formal)**
- Formal state machine with **12 states** (PRD's 7 + 5 new):
  `recibido`, `extraido`, `baja_confianza`, `error_extraccion`, `duplicado`, `validado`, `discrepancia`, `aprobado_hitl`, `rechazado`, `pendiente_escalacion`, `escalado`, `cancelado_supervisor`, `inventariado`, `error_inventario`.
- Rationale: PRD lists only 7 states; analysis surfaced 5+ missing ones (auto-HITL on low confidence, duplicate detection, ops escalation, error handling).
- Deliverable: State diagram artifact required before Sprint 1.

**D-RIPLEY-006: Idempotency anchor**
- Albarán identity = `(supplier_id, albaran_number, blob_etag)`.
- Hash check at Flow 1 entry against Cosmos `albaranes` container.
- Duplicates emit `duplicado` state and Teams notification to ops; do not re-process.
- Rationale: Re-uploads/re-scans/network retries will produce duplicate Blob events. Without dedup, double inventory entries inevitable.

**D-RIPLEY-007: Block Sprint 1 on Q1–Q12** [SATISFIED]
- No Sprint 1 build start until all 12 blocking questions answered.
- Critical-path uncertainties (BC version, capture app ownership, M365 policy, volumes, custom AL, retention/compliance) materially change architecture.

**D-RIPLEY-008: Cosmos partition key**
- Partition key = `/pk` with value `${tienda_id}_${yyyy_mm}` (composite tienda + month).
- Rationale: PRD's `/albaran.punto_entrega` produces few logical partitions = hot/cold imbalance and 20 GB partition cap concerns over multi-year retention.

**D-RIPLEY-009: Security additions**
- Prompt-injection defense: structured-output schema enforcement + Azure AI Content Safety scan on extracted text + supplier reputation tracking.
- PII redaction post-OCR (transportistas, signatures) before LLM context.
- JSON-schema validation of all MCP tool inputs before agent invocation.
- Image retention 6 years (configurable) to align with Spanish AEAT requirements (pending Q8 confirmation).
- Rationale: Supplier text is untrusted input; GDPR applies; defense in depth.

## Architecture v2 Ratified Decisions (2026-05-04)

**By:** Ripley (Lead Architect) + team consensus  
**Source:** `docs/architecture/architecture-decision-record.md`

| ID | Decision | Status |
|---|---|---|
| D-R-001 | LLMs: GPT-5.1 (Agent 1), GPT-5-mini (Agents 2 & 3); pinned versions in IaC; quarterly refresh cadence | ✅ Accepted |
| D-R-002 | OCR: Content Understanding primary, DI v4.0 fallback — final lock after Sprint 0 benchmark | ⏳ Provisional |
| D-R-003 | Inter-flow eventing: Service Bus + Durable Functions; Cosmos = data-of-record only, never a trigger | ✅ Accepted |
| D-R-004 | HITL channel: email via WorkIQ (Kiko's directive); Power Automate Approvals as plug-compatible fallback | ⏳ Provisional pending implementation |
| D-R-005 | State machine: 13 canonical states (+1 ops `cancelado_supervisor`) | ✅ Accepted |
| D-R-006 | Idempotency: two-stage (`blob_etag` at Flow 0, `supplier_id+albaran_number` at Flow 1 close) | ✅ Accepted |
| D-R-007 | Cosmos partition key `/pk = tienda_id_yyyymm` | ✅ Accepted |
| D-R-008 | Region: Sweden Central, single primary; DR posture deferred post-MVP | ✅ Accepted |
| D-R-009 | Tolerance: 2% global (qty + price, line-level) | ✅ Accepted |
| D-R-010 | Canonical albarán identity: `(supplier_id, albaran_number)`; multiple albaranes per PO allowed | ✅ Accepted |
| D-R-011 | Security: coherence validation only (PO/supplier/dates); no digital signature verification | ✅ Accepted |
| D-R-012 | All infrastructure in private VNet; self-hosted GH runners (ACA Jobs) for CI/CD bootstrap | ✅ Accepted |
| D-R-013 | MCP: Native BC MCP (read + scoped write). Custom MCPs only for Cosmos write, Content Understanding, WorkIQ | ✅ Accepted |
| D-R-014 | No DELETE on any MCP server | ✅ Accepted |
| D-R-015 | Pin LLM model versions; no `latest`, quarterly refresh | ✅ Accepted |
| D-R-016 | 6-year immutable retention on `albaranes-raw` Blob (AEAT alignment) | ✅ Accepted |
| D-R-017 | No LLM cost ceiling at MVP; budget alerts mandatory; monthly cost review | ✅ Accepted |
| D-R-018 | BC integration via standard MCP entities; Posted Purchase Receipt as success artifact; custom AL only if Burke proves Warehouse Receipt necessary | ⏳ Provisional |

## Private Networking & CI/CD Bootstrap (2026-05-03)

**By:** Brett (Network Architect)  
**Source:** `prerequisites/analysis/brett-private-networking.md`

**D-BRETT-001: Phased bootstrap model for private Azure deployment**
- Phase 0: deploy VNet, ACA runner environment, runner job, DNS scaffolding.
- Phase 1: add Private Endpoints and Private DNS, validate private resolution, disable public access.
- Phase 2: all subsequent deployments run from ACA self-hosted runners.
- Rationale: Avoids chicken-and-egg IaC deployment problem.

**D-BRETT-002: ACA Jobs as private GitHub Actions runner platform**
- Use **event-driven ACA Jobs** with GitHub runner scale rule.
- Do **not** use always-on ACA Apps as default runner model.
- Rationale: Cost efficiency and event-driven architecture.

**D-BRETT-003: Separation of CI/CD runners from product workloads**
- One internal ACA environment for runtime workloads.
- One dedicated ACA environment for runner jobs.
- Rationale: Isolation, scale independence, security posture.

**D-BRETT-004: Workload-profile ACA environments**
- Standardize on workload-profile ACA environments (not legacy consumption-only).
- Required for UDR/NAT support.
- Rationale: Private networking support and controlled egress.

**D-BRETT-005: Controlled public egress, not public ingress**
- Private inbound to all target Azure data services.
- Outbound from ACA subnets through NAT Gateway or Azure Firewall.
- Explicitly accept GitHub SaaS requires outbound internet access.
- Rationale: GDPR compliance, controlled blast radius.

**D-BRETT-006: Docker-in-Docker limitations**
- ACA Jobs cannot run Docker-in-Docker.
- Container-image builds: use ACR Tasks / `az acr build` or separate VM-based runner pool.
- Rationale: ACA Jobs platform constraint.

**D-BRETT-007: Private DNS as core IaC baseline**
- Required zones: Cosmos NoSQL, Blob, Key Vault, Azure OpenAI, AI Services / Foundry, ACA, Service Bus (if used).
- DNS validation required before disabling public access.
- Rationale: Prevents DNS leakage, enables private resolution validation.

**D-BRETT-008: Foundry Agent Service private networking exception**
- Private networking supported in Sweden Central.
- Hosted-agent network injection decided at resource creation time.
- Hosted-agent ACR cannot currently be private-only (limitation).
- Rationale: Transparency on platform constraints.

**Open flags for Kiko review (pending):**
- Is explicit GitHub public egress dependency acceptable?
- Docker builds: second runner pool or ACR Tasks?
- Service Bus: Premium tier approved for private endpoints?

### 2026-05-04: MAF Multi-Agent Orchestration Pattern Selection
**From:** Ash (MAF Specialist)
**Date:** 2026-05-04
**Priority:** HIGH — blocks agent architecture design
**Status:** PROPOSED

**Context:** Kiko asked us to rethink agent design for a potentially 5-8 agent pipeline. Researched all MAF v1.0 orchestration patterns.

**Decision:** Use **WorkflowBuilder** + **CosmosCheckpointStorage** as primary pattern.

**Rationale:**
- Our albaran pipeline is a well-defined business process with known branching (valid → post, discrepancy → escalate).
- `WorkflowBuilder` supports conditional edges (`add_switch_case_edge_group`) without LLM overhead.
- Native checkpoint/resume via `CosmosCheckpointStorage` handles 24h HITL waits.
- ACA can scale to zero during HITL waits (no idle compute).
- Lowest token cost (routing is deterministic, not LLM-decided).

**Hosting:** FastAPI in ACA (single container to start).
- All agents in one ACA container with FastAPI endpoints.
- Event Grid webhooks for blob-created and HITL-response triggers.
- Future: split into per-agent ACA containers with A2A if scaling requires it.

**Alternative:** `MagenticBuilder` (supervisor) — consider if requirements evolve and routing becomes dynamic/unpredictable (higher token cost but more adaptive).

**Key findings:**
1. HITL without Durable Functions: WorkflowBuilder checkpoints to Cosmos → ACA scales to zero → webhook resumes from checkpoint. More efficient than Durable Functions for 24h email waits.
2. A2A protocol: Standard way for agents in separate ACA containers to communicate (uses HTTP/JSON-RPC + Agent Cards). Interoperable with Google ADK, CrewAI, LangGraph.
3. Service Bus integration: Not built into MAF but trivially added as agent tools. Better suited for load-leveling than agent-to-agent communication.

**Full analysis:** See `prerequisites/analysis/ash-maf-multiagent-patterns.md`

### 2026-05-04: ACS Email for HITL — Formal Feasibility
**From:** Newt (MCP Analyst)
**Date:** 2026-05-04
**Status:** PROPOSED

**Proposed Decision:** Adopt **Azure Communication Services Email + Container App web form** as the preferred custom HITL path if the team values full Python control and wants to avoid Power Automate.

**Why:**
- ACS Email can send rich HTML email directly from Python.
- Azure MCP already exposes `communication_email_send` with HTML support.
- Custom sender domains are supported.
- Email service cost is low.
- `Modify` is cleaner in a normal web form than in Outlook cards/approval flows.

**Required caveats:**
- Reminders, timeout, escalation, and approval SLA logic must be implemented in our orchestrator layer.
- Approval links/web UI still need a secure reachable edge; this is not a purely private-only human flow unless users are on VPN/internal access.
- ACS network hardening exists, but the documented Network Security Perimeter email setup is preview.
- Tokens, auth, replay protection, and audit logging are mandatory.

**Recommendation:**
- **Preferred custom path:** ACS Email + web form + orchestrator timers.
- **Fallback path:** Power Automate approval email + backend callback + web form for Modify.

### 2026-05-04: Agentic Redesign 3→6 Agents + ADR v3
**From:** Ripley (Lead Architect)
**Date:** 2026-05-04
**Trigger:** Kiko's challenge — "¿sólo 3 agentes? Pensemos de forma transgresora."
**Status:** PROPOSED — pending team review

**Files:**
- `prerequisites/analysis/ripley-agentic-redesign.md` (new — 3→6 agent justification)
- `docs/architecture/architecture-decision-record.md` (rewritten as v3 — all Durable Functions removed, all-ACA + Service Bus, 6-agent roster, ACS Email HITL)

**Decisions to record:**

**D-R-019 (rewritten) — Hosting model: 100% ACA + MAF SDK in-process**
- **What:** All AI agents (A1–A6 at MVP, A7–A8 deferred) run inside Azure Container Apps using the MAF SDK in-process. Foundry is the Azure OpenAI model + telemetry endpoint, nothing more. **No Foundry-hosted agents. No Durable Functions.**
- **Why:** Kiko's directive (2026-05-03 23:07/23:10). Single compute plane, single orchestration framework, single VNet integration story. MAF HandOff (required for A2→A5 routing) is a MAF-SDK in-process concern.

**D-R-003 (rewritten) — Eventing & state without Durable Functions**
- **What:** Service Bus topic `albaran-events` for state-change events; Cosmos for state; **Service Bus scheduled messages** for HITL 24h/48h/72h timers (cancelled when `hitl.response.*` arrives early via `CancelScheduledMessageAsync`).
- **Why:** Same Kiko directive. Replaces every Durable Functions primitive with simpler ACA + Service Bus + Cosmos building blocks.

**D-R-020 — Agent roster: 6 at MVP + 2 deferred (rejecting PRD's 3)**
- **What:** A1 Extractor (GPT-5.1), A2 Triage (rule-based MVP), A3 Coherence (GPT-5-mini), A4 Validator (GPT-5-mini), A5 Inventory (GPT-5-mini, `require_approval=always` on Post Purchase Receipt), A6 Communication (GPT-5-mini, all outbound). Deferred: A7 Reconciliation (MVP+1), A8 Learning (MVP+2).
- **Why:** The PRD's 3-agent design bundled 5 distinct concerns (routing, coherence, communication, reconciliation, learning) into Agent 2 + the orchestrator. A truly agentic system separates them. Cost impact ≈ €0; complexity +25%; agentic value +200%.

**D-R-021 — Triage Agent (A2) is rule-based at MVP**
- **What:** A2 is a MAF agent with a deterministic `route_decision()` tool plus Cosmos-backed feature flags. LLM upgrade optional at MVP+1 once A8 produces supplier-reputation data.
- **Why:** Routing-policy explainability outweighs sophistication at launch.

**D-R-022 — Coherence (A3) is split from Validator (A4)**
- **What:** A3 = world sanity (PO exists, supplier valid, dates/totals plausible). A4 = line-level Δ vs PO at 2%. Different MCP scopes, different failure routing (A3 fails → ops CC; A4 fails → HITL approval).
- **Why:** Different prompts, different failure modes, different escalation paths. Bundling them was wrong.

**D-R-023 — Communication (A6) is event-driven, not a HandOff target**
- **What:** A6 runs in a separate ACA app (`communication-agent`), subscribes to `albaran.discrepancia / .baja_confianza / .error_validacion / .escalado / .error_inventario`. On `hitl.response.aprobado_hitl` it publishes back to the bus and the orchestrator's "resume-at-A5" subscription picks up A5 only.
- **Why:** HandOff is synchronous/in-memory. HITL is hours-to-days asynchronous. Modeling A6 as a HandOff target would force keeping workflow state in memory for 72h.

**D-R-024 — HITL timers via Service Bus scheduled messages**
- **What:** 24h reminder, 48h escalation, 72h hard-cap implemented as `ScheduleMessageAsync` calls; cancelled via `CancelScheduledMessageAsync` when `hitl.response.*` arrives early.
- **Why:** Replaces Durable Functions timers. Native to Service Bus; survives restarts; cancellable.

**D-R-025 — A7 Reconciliation deferred to MVP+1; A8 Learning deferred to MVP+2**
- **What:** Both are valuable but neither is on the critical path for "PDF in, BC posted receipt out." A8 needs ≥4 weeks of data to be useful.
- **Why:** Ship MVP honest. A8 closes the agentic loop (writes `supplier_reputation` Cosmos doc → A2 reads it for smarter routing).

**Open items:**

| # | Item | Owner |
|---|---|---|
| O-11 | Triage rule-set v1 (concrete thresholds for fast-track / normal / direct-HITL / hard-reject) | Ripley + **Lambert** (config owner) |
| O-12 | Email-template inventory (HITL initial, 24h reminder, 48h escalation, 72h ops alert, ops digest, future supplier reject) | **Newt + Lambert** |
| O-13 | Confirm Service Bus Standard tier supports 72h scheduled-message TTL | **Brett** |
| O-14 | MAF HandOff `require_per_service_call_history_persistence=True` — confirm in-memory store is sufficient for single workflow run | **Ash** |
| O-15 | A7 Reconciliation cron — KEDA cron scaler vs ACA Jobs `scheduleTriggerConfig` | **Brett** (MVP+1 planning) |
| O-16 | ACS Email private-link / Network Security Perimeter (preview) — decide edge for `hitl-webform` | **Brett + Newt** |

**Items closed:**
- O-1 reframed: "WorkIQ feasibility" → "ACS Email feasibility" (Newt still owns).
- O-5 reframed: "Foundry prompt-agent GA in Sweden Central" → "Azure OpenAI / Foundry private-net GA" (much lower risk).
- O-10 closed: Power Automate fallback no longer needed (ACS Email is the locked channel).

**Asks of the team:**
- **Ash:** PoC the in-process MAF orchestration (A1→A2→A3→A4→A5 stubs in a single ACA container) before Sprint 1 lock. Confirm O-14.
- **Brett:** Update networking topology — drop `snet-functions`, add `snet-aca-jobs`. Confirm O-13, O-15, O-16. Plan ACS Email private-link posture.
- **Newt:** Pivot ACS Email analysis to formal feasibility report covering all 6 outbound types (O-12). Validate `acs-email-mcp` server design.
- **Burke:** No change — BC MCP scope (read + scoped write Post Purchase Receipt) holds.
- **Bishop:** No change — model selection holds (GPT-5.1 for A1 only; GPT-5-mini for everything else, including the new agents).
- **Lambert:** Pre-flight on triage rules (O-11) and per-tienda approver routing by Sprint 1.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
