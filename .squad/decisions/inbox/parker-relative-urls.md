# Parker — Relative URL sweep

**Date:** 2026-05-08T00:23:20.028+02:00
**Issue:** #180, #179
**Requested by:** Kiko de Angel

## Decision summary
- Replace every remaining template `url_for()` route reference in Upload Web with literal relative paths so navigation stays on the Front Door host.
- Keep HTMX actions and browser API calls relative as well (`/mis-albaranes/filter`, `/upload/{session_id}/status`, `/api/sessions/...`) to preserve the Front Door-scoped auth cookie.
- Remove the duplicate placeholder logout handler from `src/upload_web/routes/upload.py` so `/logout` is served only by the auth route that clears the app session cookie and redirects to `/.auth/logout?post_logout_redirect_uri=/`.

## Why
- `url_for()` was emitting absolute ACA-host URLs in templates, which caused users behind Azure Front Door to hop domains and lose authenticated behavior.
- Logout needed to use the Easy Auth logout flow, not a placeholder redirect, or users could land on the wrong host / blank page.
- A complete sweep was safer than piecemeal fixes because the breakage affected normal links, HTMX polling, and filtered table actions.
