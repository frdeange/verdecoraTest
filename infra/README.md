# Infrastructure as Code

Bicep templates for Azure deployment.

- **modules/** - Reusable Bicep modules for common resources
- *.bicep - Top-level deployment templates

Deploy with: `az deployment group create -t main.bicep`

## Upload web notes

- Create the Microsoft Entra group `verdecora-store-uploaders` manually in the Azure portal, then pass its object ID(s) through `uploadWebAllowedGroupObjectIds` when enabling Easy Auth.
- Set `enableUploadWebAuth=true` only after `verdecora-upload-web-${environment}` exists in the Container Apps environment.
- Set `enableUploadWebAppGateway=true` and configure `appGwFrontendCertificateSecretId` with a Key Vault PFX secret URI before deploying the Application Gateway HTTPS listener.
