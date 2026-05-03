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

### 2026-05-03: HITL Channel — Email via WorkIQ
**By:** Kiko de Angel (updated from PRD)
**What:** Use EMAIL via WorkIQ instead of Teams Adaptive Cards or Power Automate Approvals. WorkIQ sends emails with accept/reject/modify buttons. NO Teams bot.
**Why:** User preference simplifies infrastructure and avoids tenant policy risk on custom bots.

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

### 2026-05-03: Foundry Agent Service as Primary Platform
**By:** Call (Foundry Architect)
**What:** Treat **Azure AI Foundry Agent Service** as primary platform for agent lifecycle, identity, tracing, evaluation, publishing.
- **Foundry:** prompt agents first; hosted agents only when custom runtime logic required.
- **Container Apps/Functions:** Event Grid and Change Feed adapters, webhook processors, private MCP servers.
- Prefer **prompt agents** where possible for most stable production path.
- If adopting **hosted agents**, do so knowingly under preview constraints.
- Require **Application Insights** from day one.
- Require **`allowed_tools`** and approval policies for MCP integrations.
**Why:** Service is GA at platform level. Official docs mark hosted agents/workflow agents/non-prompt tracing as preview. Container Apps is better place for event adapters and webhook receivers.
**Follow-up:** Decide whether project needs hosted agent runtime or whether prompt agents + remote MCP tools cover MVP.

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

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
