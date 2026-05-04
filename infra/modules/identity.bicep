targetScope = 'resourceGroup'

@description('Deployment location for managed identity and RBAC resources.')
param location string = resourceGroup().location

@description('Optional tags applied to every managed identity.')
param tags object = {}

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

@description('Optional Azure OpenAI account name for granting data-plane access to the ACA identity.')
param openAiAccountName string = ''

@description('Optional Document Intelligence account name for granting data-plane access to the ACA identity.')
param docIntellAccountName string = ''

@description('Optional suffix appended to the managed identity names.')
param nameSuffix string = ''

@description('When true, create the legacy user-assigned identities and their RBAC assignments.')
param deployUserAssignedIdentities bool = true

@description('Optional system-assigned principal id for the agentic orchestrator ACA app.')
param orchestratorPrincipalId string = ''

@description('Optional system-assigned principal id for the HITL web form ACA app.')
param hitlWebformPrincipalId string = ''

@description('Optional system-assigned principal id for the Flow 0 dedup ACA Job.')
param flow0WorkerPrincipalId string = ''

var cosmosBuiltInDataContributorRoleDefinitionId = '00000000-0000-0000-0000-000000000002'
var serviceBusDataSenderRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
var serviceBusDataReceiverRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'e36647ef-1570-4e4c-ae03-a6bda23981cb')
var storageBlobDataReaderRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
var storageBlobDataContributorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var keyVaultSecretsUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
var contributorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')
var communicationServicesContributorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2495237a-0d06-4fc0-b5ef-8a60a7cb5773')
var cognitiveServicesOpenAIUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
var cognitiveServicesUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')

var agenticOrchestratorIdentityName = empty(nameSuffix) ? 'agentic-orchestrator' : 'agentic-orchestrator-${nameSuffix}'
var communicationAgentIdentityName = empty(nameSuffix) ? 'communication-agent' : 'communication-agent-${nameSuffix}'
var hitlWebformIdentityName = empty(nameSuffix) ? 'hitl-webform' : 'hitl-webform-${nameSuffix}'
var flow0WorkerIdentityName = empty(nameSuffix) ? 'flow0-worker' : 'flow0-worker-${nameSuffix}'

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

resource communicationService 'Microsoft.Communication/communicationServices@2023-04-01' existing = if (!empty(communicationServiceName)) {
  name: communicationServiceName
}

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = if (!empty(openAiAccountName)) {
  name: openAiAccountName
}

resource docIntellAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = if (!empty(docIntellAccountName)) {
  name: docIntellAccountName
}

resource agenticOrchestratorIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (deployUserAssignedIdentities) {
  name: agenticOrchestratorIdentityName
  location: location
  tags: union(tags, {
    service: 'agentic-orchestrator'
    securityBoundary: 'identity-rbac'
  })
}

resource communicationAgentIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (deployUserAssignedIdentities) {
  name: communicationAgentIdentityName
  location: location
  tags: union(tags, {
    service: 'communication-agent'
    securityBoundary: 'identity-rbac'
  })
}

resource hitlWebformIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (deployUserAssignedIdentities) {
  name: hitlWebformIdentityName
  location: location
  tags: union(tags, {
    service: 'hitl-webform'
    securityBoundary: 'identity-rbac'
  })
}

resource flow0WorkerIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (deployUserAssignedIdentities) {
  name: flow0WorkerIdentityName
  location: location
  tags: union(tags, {
    service: 'flow0-worker'
    securityBoundary: 'identity-rbac'
  })
}

resource agenticOrchestratorCosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (deployUserAssignedIdentities) {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, agenticOrchestratorIdentity!.name, cosmosBuiltInDataContributorRoleDefinitionId)
  properties: {
    principalId: agenticOrchestratorIdentity!.properties.principalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosBuiltInDataContributorRoleDefinitionId}'
    scope: cosmosAccount.id
  }
}

resource communicationAgentCosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (deployUserAssignedIdentities) {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, communicationAgentIdentity!.name, cosmosBuiltInDataContributorRoleDefinitionId)
  properties: {
    principalId: communicationAgentIdentity!.properties.principalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosBuiltInDataContributorRoleDefinitionId}'
    scope: cosmosAccount.id
  }
}

resource hitlWebformCosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (deployUserAssignedIdentities) {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, hitlWebformIdentity!.name, cosmosBuiltInDataContributorRoleDefinitionId)
  properties: {
    principalId: hitlWebformIdentity!.properties.principalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosBuiltInDataContributorRoleDefinitionId}'
    scope: cosmosAccount.id
  }
}

resource flow0WorkerCosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (deployUserAssignedIdentities) {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, flow0WorkerIdentity!.name, cosmosBuiltInDataContributorRoleDefinitionId)
  properties: {
    principalId: flow0WorkerIdentity!.properties.principalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosBuiltInDataContributorRoleDefinitionId}'
    scope: cosmosAccount.id
  }
}

resource agenticOrchestratorServiceBusSenderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployUserAssignedIdentities) {
  name: guid(serviceBusNamespace.id, agenticOrchestratorIdentity!.name, serviceBusDataSenderRoleDefinitionId)
  scope: serviceBusNamespace
  properties: {
    principalId: agenticOrchestratorIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataSenderRoleDefinitionId
  }
}

resource agenticOrchestratorServiceBusReceiverRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployUserAssignedIdentities) {
  name: guid(serviceBusNamespace.id, agenticOrchestratorIdentity!.name, serviceBusDataReceiverRoleDefinitionId)
  scope: serviceBusNamespace
  properties: {
    principalId: agenticOrchestratorIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataReceiverRoleDefinitionId
  }
}

resource communicationAgentServiceBusSenderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployUserAssignedIdentities) {
  name: guid(serviceBusNamespace.id, communicationAgentIdentity!.name, serviceBusDataSenderRoleDefinitionId)
  scope: serviceBusNamespace
  properties: {
    principalId: communicationAgentIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataSenderRoleDefinitionId
  }
}

resource hitlWebformServiceBusSenderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployUserAssignedIdentities) {
  name: guid(serviceBusNamespace.id, hitlWebformIdentity!.name, serviceBusDataSenderRoleDefinitionId)
  scope: serviceBusNamespace
  properties: {
    principalId: hitlWebformIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataSenderRoleDefinitionId
  }
}

resource flow0WorkerServiceBusSenderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployUserAssignedIdentities) {
  name: guid(serviceBusNamespace.id, flow0WorkerIdentity!.name, serviceBusDataSenderRoleDefinitionId)
  scope: serviceBusNamespace
  properties: {
    principalId: flow0WorkerIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataSenderRoleDefinitionId
  }
}

resource agenticOrchestratorBlobReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployUserAssignedIdentities) {
  name: guid(storageAccount.id, agenticOrchestratorIdentity!.name, storageBlobDataReaderRoleDefinitionId)
  scope: storageAccount
  properties: {
    principalId: agenticOrchestratorIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataReaderRoleDefinitionId
  }
}

resource flow0WorkerBlobReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployUserAssignedIdentities) {
  name: guid(storageAccount.id, flow0WorkerIdentity!.name, storageBlobDataReaderRoleDefinitionId)
  scope: storageAccount
  properties: {
    principalId: flow0WorkerIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataReaderRoleDefinitionId
  }
}

resource hitlWebformBlobContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployUserAssignedIdentities) {
  name: guid(storageAccount.id, hitlWebformIdentity!.name, storageBlobDataContributorRoleDefinitionId)
  scope: storageAccount
  properties: {
    principalId: hitlWebformIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataContributorRoleDefinitionId
  }
}

resource agenticOrchestratorKeyVaultSecretsUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployUserAssignedIdentities && !empty(keyVaultName)) {
  name: guid(keyVault.id, agenticOrchestratorIdentity!.name, keyVaultSecretsUserRoleDefinitionId)
  scope: keyVault
  properties: {
    principalId: agenticOrchestratorIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

resource communicationAgentKeyVaultSecretsUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployUserAssignedIdentities && !empty(keyVaultName)) {
  name: guid(keyVault.id, communicationAgentIdentity!.name, keyVaultSecretsUserRoleDefinitionId)
  scope: keyVault
  properties: {
    principalId: communicationAgentIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

resource hitlWebformKeyVaultSecretsUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployUserAssignedIdentities && !empty(keyVaultName)) {
  name: guid(keyVault.id, hitlWebformIdentity!.name, keyVaultSecretsUserRoleDefinitionId)
  scope: keyVault
  properties: {
    principalId: hitlWebformIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

resource flow0WorkerKeyVaultSecretsUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployUserAssignedIdentities && !empty(keyVaultName)) {
  name: guid(keyVault.id, flow0WorkerIdentity!.name, keyVaultSecretsUserRoleDefinitionId)
  scope: keyVault
  properties: {
    principalId: flow0WorkerIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

resource communicationAgentCommunicationServicesContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployUserAssignedIdentities && !empty(communicationServiceName)) {
  name: guid(communicationService.id, communicationAgentIdentity!.name, communicationServicesContributorRoleDefinitionId)
  scope: communicationService
  properties: {
    principalId: communicationAgentIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: communicationServicesContributorRoleDefinitionId
  }
}

resource agenticOrchestratorCommunicationServicesContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployUserAssignedIdentities && !empty(communicationServiceName)) {
  name: guid(communicationService.id, agenticOrchestratorIdentity!.name, contributorRoleDefinitionId)
  scope: communicationService
  properties: {
    principalId: agenticOrchestratorIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: contributorRoleDefinitionId
  }
}

resource agenticOrchestratorOpenAiUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployUserAssignedIdentities && !empty(openAiAccountName)) {
  name: guid(openAiAccount.id, agenticOrchestratorIdentity!.name, cognitiveServicesOpenAIUserRoleDefinitionId)
  scope: openAiAccount
  properties: {
    principalId: agenticOrchestratorIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: cognitiveServicesOpenAIUserRoleDefinitionId
  }
}

resource agenticOrchestratorDocIntellUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployUserAssignedIdentities && !empty(docIntellAccountName)) {
  name: guid(docIntellAccount.id, agenticOrchestratorIdentity!.name, cognitiveServicesUserRoleDefinitionId)
  scope: docIntellAccount
  properties: {
    principalId: agenticOrchestratorIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: cognitiveServicesUserRoleDefinitionId
  }
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

resource orchestratorSystemAssignedOpenAiRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(orchestratorPrincipalId) && !empty(openAiAccountName)) {
  name: guid(openAiAccount.id, orchestratorPrincipalId, cognitiveServicesOpenAIUserRoleDefinitionId, 'system')
  scope: openAiAccount
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

output identities object = deployUserAssignedIdentities ? {
  agenticOrchestrator: {
    name: agenticOrchestratorIdentity!.name
    clientId: agenticOrchestratorIdentity!.properties.clientId
    principalId: agenticOrchestratorIdentity!.properties.principalId
    resourceId: agenticOrchestratorIdentity!.id
  }
  communicationAgent: {
    name: communicationAgentIdentity!.name
    clientId: communicationAgentIdentity!.properties.clientId
    principalId: communicationAgentIdentity!.properties.principalId
    resourceId: communicationAgentIdentity!.id
  }
  hitlWebform: {
    name: hitlWebformIdentity!.name
    clientId: hitlWebformIdentity!.properties.clientId
    principalId: hitlWebformIdentity!.properties.principalId
    resourceId: hitlWebformIdentity!.id
  }
  flow0Worker: {
    name: flow0WorkerIdentity!.name
    clientId: flow0WorkerIdentity!.properties.clientId
    principalId: flow0WorkerIdentity!.properties.principalId
    resourceId: flow0WorkerIdentity!.id
  }
} : {
  orchestratorSystemAssignedPrincipalId: orchestratorPrincipalId
  hitlWebformSystemAssignedPrincipalId: hitlWebformPrincipalId
  flow0WorkerSystemAssignedPrincipalId: flow0WorkerPrincipalId
}

