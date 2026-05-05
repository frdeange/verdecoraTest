# Brett — History

## Project Context
- **Project:** Sistema Inteligente de Gestión de Albaranes
- **User:** Kiko de Angel
- **Role:** Private Network & CI/CD Specialist
- **Stack:** Azure VNet, Private Endpoints, ACA self-hosted runners, Private DNS, NAT Gateway
- **Region:** Sweden Central
- **PRD:** prerequisites/pliego-tecnico-albaranes.html

## Learnings

### 2026-05-03 — Private networking + ACA runners viability
- Researched Microsoft-documented self-hosted GitHub Actions runners on **Azure Container Apps Jobs** for Sweden Central private-network deployment.
- Confirmed the pattern is viable for **private IaC/control-plane deployment**, but **not** for Docker-heavy workflows because ACA Jobs do not support Docker-in-Docker.
- Recommended a phased bootstrap: deploy runner control plane first, then add Private Endpoints + DNS, then disable public access and move all later deployments onto self-hosted runners.
- Recommended two ACA workload-profile environments: one for app workloads and one for runner jobs, plus a dedicated private-endpoint subnet.
- Captured service compatibility/caveats for Cosmos DB, Blob, Key Vault, Azure OpenAI, Document Intelligence, Foundry Agent Service, ACA, and Service Bus in `prerequisites/analysis/brett-private-networking.md`.

### 2026-05-04 — Runner bootstrap implementation for issue #4
- Imported Dallas's base `resource-group`, `network`, and `keyvault` Bicep modules onto `squad/4-vnet-runners` so the runner bootstrap can start from `master` without waiting for PR #52 to merge.
- Added `infra/modules/runners.bicep` with an internal ACA managed environment on `snet-runners`, a user-assigned managed identity, Key Vault-backed PAT secret wiring, and an ACA Job that uses the `github-runner` KEDA scaler.
- Added `infra/bootstrap/bootstrap.bicep` and `infra/bootstrap/bootstrap.ps1` for the Phase 0 bootstrap path, including manual runner execution plus GitHub API verification.
- Documented the operational flow in `docs/operations/bootstrap-guide.md`, including the explicit requirement that all later deployments move onto the self-hosted runner after bootstrap and that temporary public access is removed after private cutover.

### 2026-05-05 — App Gateway + Easy Auth landing zone for upload-web
- Added a dedicated `appgw-snet` (/24) and locked-down NSG shape for Azure Application Gateway v2 so the ACA environment can stay private while upload-web gets a controlled public ingress path.
- Added `infra/modules/appgw.bicep` wiring for Standard_v2 autoscale, HTTP→HTTPS redirect, `/healthz` probing, backend HTTPS to the ACA internal FQDN, and Key Vault-backed TLS certificate access via managed identity.
- Added `infra/modules/upload-web-auth.bicep` so Easy Auth can be switched on for `verdecora-upload-web-${environment}` with Entra audiences plus optional `verdecora-store-uploaders` group enforcement once the app exists.
- Documented that the Entra group itself must still be created manually in the Azure portal before rollout.
