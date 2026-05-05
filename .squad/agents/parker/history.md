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
