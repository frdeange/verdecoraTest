# Parker — History

## Project Context
- **Project:** Sistema Inteligente de Gestión de Albaranes
- **User:** Kiko de Angel
- **Role:** Backend Developer
- **Stack:** Python (FastAPI), Azure Container Apps, Cosmos DB Change Feed, Teams Bot, Adaptive Cards
- **PRD:** prerequisites/pliego-tecnico-albaranes.html

## Learnings

### 2026-05-06 — Upload Web scaffold + shared auth
- Added a new `src/upload_web/` FastAPI scaffold with `healthz`/`readyz`, placeholder upload routes, Jinja base layout, Verdecora CSS tokens, and the canonical logo asset.
- Introduced `src/shared/auth/` for Easy Auth header decoding (`X-MS-TOKEN-AAD-ID-TOKEN`) so Upload Web has a reusable Entra identity dependency and HITL can start consuming shared claim helpers.
- `UploadWebSettings` uses `pydantic-settings` and accepts both issue-level env names (`BLOB_ACCOUNT`, `COSMOS_URL`, `APP_INSIGHTS_CONNECTION_STRING`) and proposal/IaC env names (`STORAGE_ACCOUNT_URL`, `COSMOS_ENDPOINT`, `APPLICATIONINSIGHTS_CONNECTION_STRING`).

### 2026-05-06 — Sprint 1: branded Jinja pages + upload session API
- Reworked `src/upload_web/templates/` into a proper Jinja layout with reusable header/footer/flash partials, Tailwind/HTMX/Alpine CDNs, and dedicated `pages/home.html` + `pages/upload.html` views branded for Verdecora store staff.
- Updated Upload Web routes so authenticated users land on a friendly home screen, can open a visual upload placeholder, and still reach the existing Mis Albaranes placeholder path.
- Added `src/upload_web/models/upload.py` and `src/upload_web/services/upload_session.py` for in-memory upload sessions plus one-hour SAS issuance. For local/dev without `STORAGE_ACCOUNT_URL`, the service returns a deterministic mock SAS token.
- Added `POST /api/sessions` and `GET /api/sessions/{session_id}` under `src/upload_web/routes/api.py`, guarded by shared Easy Auth dependencies.
- Added unit coverage for template rendering and upload session creation/retrieval, including mocked Azure SAS generation.

### 2026-05-07 — Orchestrator E2E coverage + private blob OCR fix
- Fixed `src/agents/factory.py` to use the current Agent Framework import path/signature, and set GPT-5-safe default generation limits through `max_tokens` so the SDK emits `max_completion_tokens`.
- Fixed orchestrator queue parsing so it can deserialize raw Event Grid `BlobCreated` messages directly, not only Flow 0 forwarded extraction payloads.
- Fixed orchestrator OCR to analyze downloaded blob bytes (base64) instead of raw blob URLs, which is required for private Storage accounts.
- Added `tests/integration/test_orchestrator_e2e.py` for a live Azure path (Storage + Service Bus + Doc Intelligence + GPT pipeline) gated by `RUN_LIVE_AZURE_TESTS=1`; from this runner the live Service Bus test is skipped because the namespace blocks this IP at the data plane.
