# Brett — App Gateway + Easy Auth

## What changed
- Added a dedicated `appgw-snet` (`10.10.6.0/24`) and locked NSG rules so Application Gateway v2 has its own subnet and only accepts Internet 80/443 plus GatewayManager maintenance traffic.
- Added `infra/modules/appgw.bicep` for the upload-web edge: Standard_v2 autoscale, HTTP→HTTPS redirect, `/healthz` probe, HTTPS backend to the ACA internal FQDN, and Key Vault-backed frontend TLS via managed identity.
- Added `infra/modules/upload-web-auth.bicep` plus `uploadWebEntraClientId`/group audience parameters in `infra/modules/main.bicep` so Easy Auth can be enabled once `verdecora-upload-web-${environment}` exists.

## Decision
- Keep the ACA environment private and front upload-web with Application Gateway on a dedicated subnet.
- Gate Easy Auth rollout behind an explicit flag until the upload-web container app exists, while documenting the required manual Entra group creation (`verdecora-store-uploaders`) in `infra/README.md`.

## Why
- This preserves the private-network-first architecture from the approved proposal while letting Sprint 0 land the edge and auth IaC safely ahead of the app workload.
- The manual Entra group step remains outside Bicep, so the deployment notes must carry that operational dependency.
