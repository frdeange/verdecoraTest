# Infrastructure as Code

Bicep templates for Azure deployment.

- **modules/** - Reusable Bicep modules for common resources
- *.bicep - Top-level deployment templates

Deploy with: `az deployment group create -t main.bicep`

## Upload web notes

- Set `enableUploadWeb=true` to deploy the private `verdecora-upload-web-${environment}` Container App into the shared ACA environment.
- Set `uploadWebEntraClientId` to the Microsoft Entra app registration client ID for `Verdecora Upload Web`, and configure the redirect URI `https://upload-web-d3hpbffsfwercgcv.b02.azurefd.net/.auth/login/aad/callback`.
- Create the Microsoft Entra group `verdecora-store-uploaders` manually in the Azure portal, then pass its object ID(s) through `uploadWebAllowedGroupObjectIds` when enabling Easy Auth.
- Set `enableUploadWebAuth=true` only after `verdecora-upload-web-${environment}` exists in the Container Apps environment.
- Set `enableUploadWebAppGateway=true` and configure `appGwFrontendCertificateSecretId` with a Key Vault PFX secret URI before deploying the Application Gateway HTTPS listener.
- The upload UI session metadata now lives in the Cosmos `upload-sessions` container (TTL 24h, partition key `/user_oid`).
