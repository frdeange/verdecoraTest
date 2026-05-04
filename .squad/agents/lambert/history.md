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
