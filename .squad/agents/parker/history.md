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

### 2026-05-07 — Orchestrator E2E integration + Sprint 0 closure
- Created `tests/integration/test_orchestrator.py` with 3 passing integration tests: orchestrator health, OCR blob → extract → classify pipeline, Event Grid message routing via Service Bus.
- Fixed OCR blob analysis handler: now correctly parses event payload and triggers extraction.
- Fixed queue handler: Event Grid messages routed through Service Bus correctly consumed by orchestrator.
- Validated WorkflowBuilder pattern with deterministic routing (no HandoffBuilder overhead needed at A1/A2 stage).
- **Team decision:** Orchestrator pattern locked. PR #165 merged; ready for Sprint 1 agent expansion (A3–A6).
- **Team context:** Dallas Event Grid integration complete (PR #167). Bishop A1/A2 agents validated. Store catalog + detector unified in PR #129. All Sprint 0 dependencies clear for Sprint 1 agent development.
### 2026-05-07 — Orchestrator E2E coverage + private blob OCR fix
- Fixed `src/agents/factory.py` to use the current Agent Framework import path/signature, and set GPT-5-safe default generation limits through `max_tokens` so the SDK emits `max_completion_tokens`.
- Fixed orchestrator queue parsing so it can deserialize raw Event Grid `BlobCreated` messages directly, not only Flow 0 forwarded extraction payloads.
- Fixed orchestrator OCR to analyze downloaded blob bytes (base64) instead of raw blob URLs, which is required for private Storage accounts.
- Added `tests/integration/test_orchestrator_e2e.py` for a live Azure path (Storage + Service Bus + Doc Intelligence + GPT pipeline) gated by `RUN_LIVE_AZURE_TESTS=1`; from this runner the live Service Bus test is skipped because the namespace blocks this IP at the data plane.

### 2026-05-07 — Upload Web public landing + dashboard split
- Upload Web now supports a public landing flow: `/` and `/login` are middleware-exempt exact paths, render a branded Microsoft sign-in page, and redirect authenticated users to `/dashboard`.
- The authenticated home screen moved from `/` to `/dashboard`; templates that offer a “volver” or header-home action should target `/dashboard` for signed-in users and `/` for anonymous users.
- Upload Web coverage is currently validated with `python -m pytest tests/unit/test_jinja_templates.py tests/unit/test_session_security.py tests/unit/test_upload_web_scaffold.py tests/unit/test_upload_backend.py tests/unit/test_upload_flow.py tests/unit/test_upload_session.py tests/e2e/test_upload_web_smoke.py tests/e2e/test_upload_e2e.py -q`.

### 2026-05-07T23:33:42.986+02:00 — Easy Auth principal headers behind Front Door
- Upload Web and shared API dependencies now treat `X-MS-CLIENT-PRINCIPAL` as the canonical Easy Auth source, with fallback to `X-MS-CLIENT-PRINCIPAL-ID` + `X-MS-CLIENT-PRINCIPAL-NAME`, and only then the legacy `X-MS-TOKEN-AAD-ID-TOKEN`.
- The Easy Auth client principal is base64 JSON; normalized claims should map the Entra `nameidentifier/objectidentifier` variants into `oid`, preserve `preferred_username`/email/name, and fold repeated role/group claims into `groups`.
- Auth regression coverage now uses client-principal headers across Upload Web unit/e2e/load tests, while keeping one explicit legacy ID-token test for backward compatibility.

### 2026-05-08T00:06:25.767+02:00 — Upload Web session-first flow repair
- The upload page must create an `UploadSession` before the user selects files; `pages/upload.html` and the dropzone/button HTMX attributes depend on a concrete `session_id` and break when it renders empty.
- The browser upload client must follow the backend contract exactly: request SAS with `POST /api/sessions/{session_id}/sas?filename=...`, use `upload_url` from the response, and register metadata with `mime_type`.
- The analyze CTA should stay disabled until at least one file has finished SAS upload + backend registration, and the upload template must include the `#preflight-loading` HTMX indicator referenced by the button.

### 2026-05-08T00:23:20.028+02:00 — Upload Web relative Front Door URLs
- Upload Web templates must use literal relative paths for internal navigation/HTMX (`/dashboard`, `/upload`, `/mis-albaranes`, `/upload/{session_id}/status`, etc.); `url_for()` in Jinja can emit the ACA hostname and break Front Door cookie scope.
- The only logout handler should be the auth route that clears the upload session cookie and redirects to `/.auth/logout?post_logout_redirect_uri=/`; placeholder `/logout` redirects are not acceptable behind Front Door.
- `src/upload_web/static/js/upload.js` already follows the required pattern: all browser API calls stay relative under `/api/sessions/...`, so Front Door compatibility there is a verification point, not a new code path.

### 2026-05-08T00:58:18.381+02:00 — Upload Web real storage config + CSP
- `src/upload_web/config.py` expects `STORAGE_ACCOUNT_URL` (alias `BLOB_ACCOUNT`), `RAW_BLOB_CONTAINER`, and `UPLOAD_SESSIONS_CONTAINER` for blob upload configuration; there is no dedicated `STORAGE_ACCOUNT_NAME` env consumed by Upload Web.
- `src/upload_web/services/blob_sas.py` and `src/upload_web/services/upload_session.py` both call `BlobServiceClient(...).get_user_delegation_key(...)`, so the ACA managed identity needs Blob delegation capability in addition to the blob container config.
- Azure Container App `verdecora-upload-web-dev` was missing explicit storage env vars; configured it with `https://stalbaranesdev.blob.core.windows.net`, `albaranes-raw`, and `upload-sessions`, and ensured the system-assigned identity has `Storage Blob Data Contributor` plus `Storage Blob Delegator` on `stalbaranesdev`.
- Upload Web CSP now needs `connect-src 'self' https://*.blob.core.windows.net` so direct browser SAS uploads to Azure Blob Storage are allowed.
