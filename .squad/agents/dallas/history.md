# Dallas — History

## Project Context
- **Project:** Sistema Inteligente de Gestión de Albaranes
- **User:** Kiko de Angel
- **Role:** Azure Cloud Engineer
- **Stack:** Bicep, Azure Container Apps, Cosmos DB, Blob Storage, Event Grid, Key Vault, VNet
- **PRD:** prerequisites/pliego-tecnico-albaranes.html

## Learnings

## 2026-05-04
- Created Sprint 0 Bicep foundation modules (resource group, network, Service Bus, Cosmos DB, Storage, Key Vault, monitoring, and main orchestrator).
- Added dev/prod parameter files aligned to Sweden Central.

## 2026-05-07
- Completed Event Grid → Service Bus integration for `albaranes-raw` blob trigger.
- PR #167 opened; smoke test passed (blob-created → Service Bus message delivery).
- Ready for Sprint 1 agent orchestrator consumption of blob ingestion events.
- **Team update:** Parker's orchestrator E2E tests confirm queue handler works with Event Grid messages. Bishop validated A1/A2 agents consume blob events correctly.
- Configured Event Grid system topic eg-st-albaranes-dev to deliver Microsoft.Storage.BlobCreated events for /blobServices/default/containers/albaranes-raw/*.pdf into Service Bus queue albaran-incoming.
- For private Service Bus namespaces, Event Grid delivery required trustedServiceAccessEnabled=true plus Azure Service Bus Data Sender on the queue for the system topic managed identity.
- Azure CLI az eventgrid event-subscription create rejected managed-identity delivery for this system topic, so the working path was ARM REST with deliveryWithResourceIdentity against API version 2024-06-01-preview.
- End-to-end smoke test succeeded: uploaded a PDF to albaranes-raw and observed albaran-incoming active message count increase from 0 to 1. Temporary Storage public access/CIDR allowlist and Storage Blob Data Contributor were granted only for the smoke test and then reverted.
- Completed issue #171 ACR rollback in IaC + runtime: `acralbaranesdev` moved from Premium/private to Standard/public, `buildpool-dev` agent pool was removed, and the ACR private endpoint / `privatelink.azurecr.io` DNS assets were deleted.
- Updated `build-deploy.yml` so all five `az acr build` invocations use the registry directly without `--agent-pool`; Container Apps keep pulling through managed identity + `AcrPull`.
