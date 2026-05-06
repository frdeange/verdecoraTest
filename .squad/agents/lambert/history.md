# Lambert — History

## Project Context
- **Project:** Sistema Inteligente de Gestión de Albaranes
- **User:** Kiko de Angel
- **Role:** Security Engineer
- **Stack:** Entra ID, Managed Identities, Key Vault, Private Endpoints, OAuth 2.0
- **PRD:** prerequisites/pliego-tecnico-albaranes.html

## Learnings

### 2026-05-04 — Issue #6 identity foundation
- Added `infra/modules/identity.bicep` to create four user-assigned managed identities and bind least-privilege access through Azure RBAC plus Cosmos DB NoSQL data-plane RBAC.
- Added `infra/modules/keyvault-secrets.bicep` for placeholder secrets (`bc-oauth-client-secret`, `acs-connection-string`, `github-runner-pat`) and Key Vault diagnostics to Log Analytics.
- Added `docs/security/identity-matrix.md` to document the full service-to-role matrix, BC OAuth 2.0 + PKCE delegated configuration, and secret rotation guidance.
- Added `src/config/security.py` with MI-based helpers for Azure Identity, Key Vault, Cosmos DB, and Service Bus, plus unit coverage in `tests/unit/config/test_security.py`.

### 2026-05-05 — Issue #100 session security middleware
- Added `src/upload_web/middleware/session_security.py` with signed session cookies, 30-minute idle timeout enforcement, CSRF validation for unsafe methods, and the required response security headers.
- Wired Upload Web to use middleware-backed auth/session state, moved logout to `src/upload_web/routes/auth.py`, and redirect logout through Easy Auth after clearing the app cookie.
- Updated `src/upload_web/templates/base.html` and `src/upload_web/static/css/verdecora.css` so the logout control is highly visible and HTMX requests automatically send the server-rendered CSRF token.
- Added `tests/unit/test_session_security.py` and extended dependency config (`itsdangerous`) to cover idle timeout, CSRF, headers, and logout cookie clearing.
