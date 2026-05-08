# Dallas — Upload Web VNet recreation notes

## Decision
- Recreate `acae-upload-web-${environment}` as a dedicated **external** Container Apps managed environment on a new delegated subnet (`snet-upload-web`, `10.10.6.0/23`) instead of reusing the internal shared ACA environment.
- Keep Front Door pointed at the upload app FQDN, but make Private Link optional in `frontdoor.bicep` so upload-web can use a public ACA origin while other patterns can still reuse the module with Private Link later.
- Keep Storage private and add Blob CORS as an explicit parameter (`uploadWebBlobCorsAllowedOrigins`) rather than deriving the Front Door hostname inside Bicep, because the default `azurefd.net` hostname is generated only when Front Door is provisioned and would otherwise create a deployment cycle.

## Why
- Azure Container Apps managed environment VNet integration is immutable; the existing `acae-upload-web-dev` cannot be retrofitted with a subnet.
- Upload Web needs public ingress for Front Door while still using VNet outbound to reach private endpoints for Storage, Cosmos, Key Vault, and Document Intelligence.
- Storage must remain private, so browser uploads need a precise origin allow-list instead of reopening public access.

## Validation
- `az containerapp env list -g rg-verdecoratest-dev` showed `acae-upload-web-dev` without VNet settings, while `acae-verdecora-dev` and `acae-runners-dev` are VNet-integrated.
- `az network vnet subnet list --vnet-name vnet-albaranes-dev -g rg-verdecoratest-dev` confirmed `10.10.6.0/23` is available for the new delegated subnet.
- `az bicep build --file C:\repos\verdecoraTest\infra\modules\main.bicep` completed successfully after the changes (existing repo warnings remain).
