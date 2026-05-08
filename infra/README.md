# Infrastructure as Code

Bicep templates for Azure deployment.

- **modules/** - Reusable Bicep modules for common resources
- *.bicep - Top-level deployment templates

Deploy with: `az deployment group create -t main.bicep`

## Upload web notes

- Set `enableUploadWeb=true` to deploy `verdecora-upload-web-${environment}` into its own external ACA environment with VNet outbound through `snet-upload-web`.
- Pass the exact Front Door/custom-domain origins through `uploadWebBlobCorsAllowedOrigins` so Blob CORS allows browser `PUT` uploads while Storage stays private.
- Create the Microsoft Entra group `verdecora-store-uploaders` manually in the Azure portal, then pass its object ID(s) through `uploadWebAllowedGroupObjectIds` when enabling Easy Auth.
- Set `enableUploadWebAuth=true` only after `verdecora-upload-web-${environment}` exists in the Container Apps environment.
- Set `enableUploadWebAppGateway=true` and configure `appGwFrontendCertificateSecretId` with a Key Vault PFX secret URI before deploying the Application Gateway HTTPS listener.
- The upload UI session metadata now lives in the Cosmos `upload-sessions` container (TTL 24h, partition key `/user_oid`).
