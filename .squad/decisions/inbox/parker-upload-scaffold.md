# Parker — Upload Web scaffold decisions

## Context
Sprint 0 issue text asked for `src/upload_web/` and `src/shared/auth/`, while the earlier proposal referenced `src/services/upload_web/` and `src/services/_shared/`.

## Decisions
1. Follow the explicit issue contract for package locations: `src/upload_web/` for the new FastAPI app and `src/shared/auth/` for reusable Entra helpers.
2. Keep `hitl_webform` on its current bearer-token validation flow for now, but start consuming shared claim extraction helpers there so the auth refactor lands incrementally without breaking HITL.
3. Add `pydantic-settings` as a runtime dependency and make Upload Web settings accept both issue names (`BLOB_ACCOUNT`, `COSMOS_URL`, `APP_INSIGHTS_CONNECTION_STRING`) and existing proposal/IaC names (`STORAGE_ACCOUNT_URL`, `COSMOS_ENDPOINT`, `APPLICATIONINSIGHTS_CONNECTION_STRING`).

## Why this matters
This keeps Sprint 0 aligned with the requested issue wording, avoids a larger directory migration in the same branch, and preserves compatibility with the env names already present in the architecture proposal.
