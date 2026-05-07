# Parker — Upload flow fix notes

**Date:** 2026-05-08T00:06:25.767+02:00
**Issue:** #177
**Requested by:** Kiko de Angel

## Decision summary
- Create the upload session on `GET /upload` so the page always renders with a concrete `session_id` before any HTMX or browser upload request starts.
- Keep the existing backend API contract (`POST /api/sessions/{id}/sas?filename=...`, `POST /api/sessions/{id}/files` with `mime_type`) and align the browser client to it instead of adding a second API variant.
- Gate the “Siguiente: Analizar” action until at least one file has completed SAS upload + backend registration, avoiding preflight calls while uploads are still pending.
- Add the missing `#preflight-loading` HTMX indicator to the upload page template so the configured loading state exists in the DOM.

## Why
- The rendered upload page had an empty `session_id`, so HTMX built `/api/sessions//preflight` and the browser never had a valid session-scoped URL.
- The frontend JS also drifted from the API contract (`JSON` body for SAS, `sas_url`, `content_type`), which broke the intended create-session → upload → preflight sequence even after the empty-URL issue.
- Enabling preflight only after completed registrations matches the real flow and removes a race where users could click analyze before the files were ready server-side.
