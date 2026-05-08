targetScope = 'resourceGroup'

@description('Name of the Azure Cosmos DB account used for workflow state.')
param cosmosAccountName string

@description('Name of the Azure Service Bus namespace used for workflow events.')
param serviceBusNamespaceName string

@description('Name of the storage account that stores inbound delivery note PDFs.')
param storageAccountName string

@description('Optional name of the Key Vault that stores application secrets. The vault must already use RBAC authorization mode.')
param keyVaultName string = ''

@description('Optional name of the Azure Communication Services resource used for HITL email.')
param communicationServiceName string = ''

@description('Optional name of the Azure AI Foundry account for granting OpenAI-compatible access to the ACA identity.')
param aiServicesAccountName string = ''

@description('Optional Document Intelligence account name for granting data-plane access to the ACA identity.')
param docIntellAccountName string = ''

@description('Optional Azure Container Registry name for granting image pull access to ACA identities.')
param acrName string = ''

@description('Optional system-assigned principal id for the agentic orchestrator ACA app.')
param orchestratorPrincipalId string = ''

@description('Optional system-assigned principal id for the HITL web form ACA app.')
param hitlWebformPrincipalId string = ''

@description('Optional system-assigned principal id for the Flow 0 dedup ACA Job.')
param flow0WorkerPrincipalId string = ''

@description('Optional system-assigned principal id for the escalation timer ACA Job.')
param escalationTimerPrincipalId string = ''

@description('Optional system-assigned principal id for the upload-web ACA app.')
param uploadWebPrincipalId string = ''

var cosmosBuiltInDataContributorRoleDefinitionId = '00000000-0000-0000-0000-000000000002'
var serviceBusDataSenderRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39')
var serviceBusDataReceiverRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0')
var storageBlobDataReaderRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
var storageBlobDataContributorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var storageBlobDelegatorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'db58b8e5-c6ad-4a2a-8342-4190687cbf4a')
var keyVaultSecretsUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
var contributorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')
var acrPullRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
var cognitiveServicesOpenAIUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
var cognitiveServicesUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: cosmosAccountName
}

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2024-01-01' existing = {
  name: serviceBusNamespaceName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = if (!empty(keyVaultName)) {
  name: keyVaultName
}

resource communicationService 'Microsoft.Communication/communicationServices@2026-03-18' existing = if (!empty(communicationServiceName)) {
  name: communicationServiceName
}

resource aiServicesAccount 'Microsoft.CognitiveServices/accounts@2025-10-01-preview' existing = if (!empty(aiServicesAccountName)) {
  name: aiServicesAccountName
}

resource docIntellAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = if (!empty(docIntellAccountName)) {
  name: docIntellAccountName
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = if (!empty(acrName)) {
  name: acrName
}

resource orchestratorSystemAssignedCosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (!empty(orchestratorPrincipalId)) {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, orchestratorPrincipalId, cosmosBuiltInDataContributorRoleDefinitionId, 'system')
  properties: {
    principalId: orchestratorPrincipalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosBuiltInDataContributorRoleDefinitionId}'
    scope: cosmosAccount.id
  }
}

resource orchestratorSystemAssignedServiceBusSenderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(orchestratorPrincipalId)) {
  name: guid(serviceBusNamespace.id, orchestratorPrincipalId, serviceBusDataSenderRoleDefinitionId, 'system')
  scope: serviceBusNamespace
  properties: {
    principalId: orchestratorPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataSenderRoleDefinitionId
  }
}

resource orchestratorSystemAssignedServiceBusReceiverRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(orchestratorPrincipalId)) {
  name: guid(serviceBusNamespace.id, orchestratorPrincipalId, serviceBusDataReceiverRoleDefinitionId, 'system')
  scope: serviceBusNamespace
  properties: {
    principalId: orchestratorPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataReceiverRoleDefinitionId
  }
}

resource orchestratorSystemAssignedBlobReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(orchestratorPrincipalId)) {
  name: guid(storageAccount.id, orchestratorPrincipalId, storageBlobDataReaderRoleDefinitionId, 'system')
  scope: storageAccount
  properties: {
    principalId: orchestratorPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataReaderRoleDefinitionId
  }
}

resource orchestratorSystemAssignedAiServicesRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(orchestratorPrincipalId) && !empty(aiServicesAccountName)) {
  name: guid(aiServicesAccount.id, orchestratorPrincipalId, cognitiveServicesOpenAIUserRoleDefinitionId, 'system')
  scope: aiServicesAccount
  properties: {
    principalId: orchestratorPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: cognitiveServicesOpenAIUserRoleDefinitionId
  }
}

resource orchestratorSystemAssignedDocIntellRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(orchestratorPrincipalId) && !empty(docIntellAccountName)) {
  name: guid(docIntellAccount.id, orchestratorPrincipalId, cognitiveServicesUserRoleDefinitionId, 'system')
  scope: docIntellAccount
  properties: {
    principalId: orchestratorPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: cognitiveServicesUserRoleDefinitionId
  }
}

resource orchestratorSystemAssignedCommunicationServicesContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(orchestratorPrincipalId) && !empty(communicationServiceName)) {
  name: guid(communicationService.id, orchestratorPrincipalId, contributorRoleDefinitionId, 'system')
  scope: communicationService
  properties: {
    principalId: orchestratorPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: contributorRoleDefinitionId
  }
}

resource orchestratorSystemAssignedKeyVaultSecretsUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(orchestratorPrincipalId) && !empty(keyVaultName)) {
  name: guid(keyVault.id, orchestratorPrincipalId, keyVaultSecretsUserRoleDefinitionId, 'system')
  scope: keyVault
  properties: {
    principalId: orchestratorPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

resource flow0SystemAssignedCosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (!empty(flow0WorkerPrincipalId)) {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, flow0WorkerPrincipalId, cosmosBuiltInDataContributorRoleDefinitionId, 'system')
  properties: {
    principalId: flow0WorkerPrincipalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosBuiltInDataContributorRoleDefinitionId}'
    scope: cosmosAccount.id
  }
}

resource flow0SystemAssignedServiceBusSenderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(flow0WorkerPrincipalId)) {
  name: guid(serviceBusNamespace.id, flow0WorkerPrincipalId, serviceBusDataSenderRoleDefinitionId, 'system')
  scope: serviceBusNamespace
  properties: {
    principalId: flow0WorkerPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataSenderRoleDefinitionId
  }
}

resource flow0SystemAssignedServiceBusReceiverRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(flow0WorkerPrincipalId)) {
  name: guid(serviceBusNamespace.id, flow0WorkerPrincipalId, serviceBusDataReceiverRoleDefinitionId, 'system')
  scope: serviceBusNamespace
  properties: {
    principalId: flow0WorkerPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataReceiverRoleDefinitionId
  }
}

resource flow0SystemAssignedBlobReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(flow0WorkerPrincipalId)) {
  name: guid(storageAccount.id, flow0WorkerPrincipalId, storageBlobDataReaderRoleDefinitionId, 'system')
  scope: storageAccount
  properties: {
    principalId: flow0WorkerPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataReaderRoleDefinitionId
  }
}

resource hitlWebformSystemAssignedBlobContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(hitlWebformPrincipalId)) {
  name: guid(storageAccount.id, hitlWebformPrincipalId, storageBlobDataContributorRoleDefinitionId, 'system')
  scope: storageAccount
  properties: {
    principalId: hitlWebformPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataContributorRoleDefinitionId
  }
}

resource hitlWebformSystemAssignedBlobDelegatorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(hitlWebformPrincipalId)) {
  name: guid(storageAccount.id, hitlWebformPrincipalId, storageBlobDelegatorRoleDefinitionId, 'system')
  scope: storageAccount
  properties: {
    principalId: hitlWebformPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDelegatorRoleDefinitionId
  }
}

resource hitlWebformSystemAssignedCosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (!empty(hitlWebformPrincipalId)) {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, hitlWebformPrincipalId, cosmosBuiltInDataContributorRoleDefinitionId, 'system')
  properties: {
    principalId: hitlWebformPrincipalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosBuiltInDataContributorRoleDefinitionId}'
    scope: cosmosAccount.id
  }
}

resource hitlWebformSystemAssignedServiceBusSenderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(hitlWebformPrincipalId)) {
  name: guid(serviceBusNamespace.id, hitlWebformPrincipalId, serviceBusDataSenderRoleDefinitionId, 'system')
  scope: serviceBusNamespace
  properties: {
    principalId: hitlWebformPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataSenderRoleDefinitionId
  }
}

resource hitlWebformSystemAssignedServiceBusReceiverRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(hitlWebformPrincipalId)) {
  name: guid(serviceBusNamespace.id, hitlWebformPrincipalId, serviceBusDataReceiverRoleDefinitionId, 'system')
  scope: serviceBusNamespace
  properties: {
    principalId: hitlWebformPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataReceiverRoleDefinitionId
  }
}

resource hitlWebformSystemAssignedKeyVaultSecretsUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(hitlWebformPrincipalId) && !empty(keyVaultName)) {
  name: guid(keyVault.id, hitlWebformPrincipalId, keyVaultSecretsUserRoleDefinitionId, 'system')
  scope: keyVault
  properties: {
    principalId: hitlWebformPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

resource hitlWebformSystemAssignedCommunicationServicesContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(hitlWebformPrincipalId) && !empty(communicationServiceName)) {
  name: guid(communicationService.id, hitlWebformPrincipalId, contributorRoleDefinitionId, 'system')
  scope: communicationService
  properties: {
    principalId: hitlWebformPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: contributorRoleDefinitionId
  }
}

// The escalation timer scans Cosmos for stale HITL reviews and uses ACS to send reminder emails.
resource escalationTimerSystemAssignedCosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (!empty(escalationTimerPrincipalId)) {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, escalationTimerPrincipalId, cosmosBuiltInDataContributorRoleDefinitionId, 'system')
  properties: {
    principalId: escalationTimerPrincipalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosBuiltInDataContributorRoleDefinitionId}'
    scope: cosmosAccount.id
  }
}

resource escalationTimerSystemAssignedCommunicationServicesContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(escalationTimerPrincipalId) && !empty(communicationServiceName)) {
  name: guid(communicationService.id, escalationTimerPrincipalId, contributorRoleDefinitionId, 'system')
  scope: communicationService
  properties: {
    principalId: escalationTimerPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: contributorRoleDefinitionId
  }
}

resource orchestratorSystemAssignedAcrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(orchestratorPrincipalId) && !empty(acrName)) {
  name: guid(acr.id, orchestratorPrincipalId, acrPullRoleDefinitionId, 'system')
  scope: acr
  properties: {
    principalId: orchestratorPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

resource flow0SystemAssignedAcrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(flow0WorkerPrincipalId) && !empty(acrName)) {
  name: guid(acr.id, flow0WorkerPrincipalId, acrPullRoleDefinitionId, 'system')
  scope: acr
  properties: {
    principalId: flow0WorkerPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

resource hitlWebformSystemAssignedAcrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(hitlWebformPrincipalId) && !empty(acrName)) {
  name: guid(acr.id, hitlWebformPrincipalId, acrPullRoleDefinitionId, 'system')
  scope: acr
  properties: {
    principalId: hitlWebformPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

resource escalationTimerSystemAssignedAcrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(escalationTimerPrincipalId) && !empty(acrName)) {
  name: guid(acr.id, escalationTimerPrincipalId, acrPullRoleDefinitionId, 'system')
  scope: acr
  properties: {
    principalId: escalationTimerPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

resource uploadWebSystemAssignedBlobContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(uploadWebPrincipalId)) {
  name: guid(storageAccount.id, uploadWebPrincipalId, storageBlobDataContributorRoleDefinitionId, 'system')
  scope: storageAccount
  properties: {
    principalId: uploadWebPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataContributorRoleDefinitionId
  }
}

resource uploadWebSystemAssignedBlobDelegatorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(uploadWebPrincipalId)) {
  name: guid(storageAccount.id, uploadWebPrincipalId, storageBlobDelegatorRoleDefinitionId, 'system')
  scope: storageAccount
  properties: {
    principalId: uploadWebPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDelegatorRoleDefinitionId
  }
}

resource uploadWebSystemAssignedCosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (!empty(uploadWebPrincipalId)) {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, uploadWebPrincipalId, cosmosBuiltInDataContributorRoleDefinitionId, 'system')
  properties: {
    principalId: uploadWebPrincipalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosBuiltInDataContributorRoleDefinitionId}'
    scope: cosmosAccount.id
  }
}

resource uploadWebSystemAssignedServiceBusSenderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(uploadWebPrincipalId)) {
  name: guid(serviceBusNamespace.id, uploadWebPrincipalId, serviceBusDataSenderRoleDefinitionId, 'system')
  scope: serviceBusNamespace
  properties: {
    principalId: uploadWebPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataSenderRoleDefinitionId
  }
}

resource uploadWebSystemAssignedDocIntellRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(uploadWebPrincipalId) && !empty(docIntellAccountName)) {
  name: guid(docIntellAccount.id, uploadWebPrincipalId, cognitiveServicesUserRoleDefinitionId, 'system')
  scope: docIntellAccount
  properties: {
    principalId: uploadWebPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: cognitiveServicesUserRoleDefinitionId
  }
}

resource uploadWebSystemAssignedKeyVaultSecretsUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(uploadWebPrincipalId) && !empty(keyVaultName)) {
  name: guid(keyVault.id, uploadWebPrincipalId, keyVaultSecretsUserRoleDefinitionId, 'system')
  scope: keyVault
  properties: {
    principalId: uploadWebPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

resource uploadWebSystemAssignedAcrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(uploadWebPrincipalId) && !empty(acrName)) {
  name: guid(acr.id, uploadWebPrincipalId, acrPullRoleDefinitionId, 'system')
  scope: acr
  properties: {
    principalId: uploadWebPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

output identities object = {
  orchestratorSystemAssignedPrincipalId: orchestratorPrincipalId
  hitlWebformSystemAssignedPrincipalId: hitlWebformPrincipalId
  flow0WorkerSystemAssignedPrincipalId: flow0WorkerPrincipalId
  escalationTimerSystemAssignedPrincipalId: escalationTimerPrincipalId
  uploadWebSystemAssignedPrincipalId: uploadWebPrincipalId
}
