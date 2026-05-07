# Lambert — History

## Project Context
- **Project:** Sistema Inteligente de Gestión de Albaranes
- **User:** Kiko de Angel
- **Role:** Security Engineer
- **Stack:** Entra ID, Managed Identities, Key Vault, Private Endpoints, OAuth 2.0
- **PRD:** prerequisites/pliego-tecnico-albaranes.html

## Learnings

### 2026-05-07 — Azure exposure lockdown before E2E
- Audited `rg-verdecoratest-dev` in subscription `0acbc8a1-0f3e-498e-b86b-6fa5468730e2` to ensure only Front Door remains intentionally public before E2E.
- Re-locked `verdecora-ais-dev` (`publicNetworkAccess=Disabled`, `networkAcls.defaultAction=Deny`), disabled public access on `verdecora-docintell-dev`, removed the temporary Cosmos IP rule and disabled Cosmos public access, and disabled ACR public access.
- Confirmed `kv-albaranes-dev` and `stalbaranesdev` were already locked, and verified `sb-albaranes-dev` keeps `trustedServiceAccessEnabled=true` while public access stays disabled for Event Grid compatibility.
- Confirmed `verdecora-upload-web-dev` still has external ACA ingress with no IP restrictions; this remains the main residual public exposure besides Front Door and should be tightened later if the team wants true Front-Door-only reachability.

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
## Decisions (Team Integration — 2026-05-07)

### 2026-05-07 — Merged from decisions/inbox/lambert-security-audit.md
- **Audit of GPS Demo Subscription (rg-verdecoratest-dev) before E2E:** Public surface reduced to Front Door + Upload Web Container App FQDN as designed.
- **Locked down:** verdecora-ais-dev (publicNetworkAccess=Disabled + networkAcls.defaultAction=Deny), verdecora-docintell-dev (publicNetworkAccess=Disabled), cosmos-albaranes-dev (publicNetworkAccess=Disabled + removed temp firewall IP), acralbaranesdev (publicNetworkAccess=Disabled).
- **Already compliant:** kv-albaranes-dev, stalbaranesdev, sb-albaranes-dev (keeps trustedServiceAccessEnabled=true for Event Grid compatibility).
- **Intentionally public:** afd-verdecora-dev (Front Door by design), verdecora-upload-web-dev (ACA external ingress by design, residual exposure for future tightening).

**Follow-ups (no blockers):**
- If strict "Front Door + nothing else" policy desired: add ACA ingress restrictions or move Upload Web to private ingress with Front Door origin hardening.
