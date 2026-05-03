targetScope = 'resourceGroup'

@description('Deployment location for the user-assigned managed identities.')
param location string = resourceGroup().location

@description('Optional tags applied to every managed identity.')
param tags object = {}

@description('Name of the Azure Cosmos DB account used for workflow state.')
param cosmosAccountName string

@description('Name of the Azure Service Bus namespace used for workflow events.')
param serviceBusNamespaceName string

@description('Name of the storage account that stores inbound delivery note PDFs.')
param storageAccountName string

@description('Name of the Key Vault that stores application secrets. The vault must already use RBAC authorization mode.')
param keyVaultName string

@description('Name of the Azure Communication Services resource used for HITL email.')
param communicationServiceName string

@description('Optional suffix appended to the managed identity names.')
param nameSuffix string = ''

var cosmosBuiltInDataContributorRoleDefinitionId = '00000000-0000-0000-0000-000000000002'
var serviceBusDataSenderRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
var serviceBusDataReceiverRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'e36647ef-1570-4e4c-ae03-a6bda23981cb')
var storageBlobDataReaderRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
var keyVaultSecretsUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
var communicationServicesContributorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2495237a-0d06-4fc0-b5ef-8a60a7cb5773')

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

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource communicationService 'Microsoft.Communication/communicationServices@2023-04-01' existing = {
  name: communicationServiceName
}

resource agenticOrchestratorIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: agenticOrchestratorIdentityName
  location: location
  tags: union(tags, {
    service: 'agentic-orchestrator'
    securityBoundary: 'identity-rbac'
  })
}

resource communicationAgentIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: communicationAgentIdentityName
  location: location
  tags: union(tags, {
    service: 'communication-agent'
    securityBoundary: 'identity-rbac'
  })
}

resource hitlWebformIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: hitlWebformIdentityName
  location: location
  tags: union(tags, {
    service: 'hitl-webform'
    securityBoundary: 'identity-rbac'
  })
}

resource flow0WorkerIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: flow0WorkerIdentityName
  location: location
  tags: union(tags, {
    service: 'flow0-worker'
    securityBoundary: 'identity-rbac'
  })
}

resource agenticOrchestratorCosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, agenticOrchestratorIdentity.name, cosmosBuiltInDataContributorRoleDefinitionId)
  properties: {
    principalId: agenticOrchestratorIdentity.properties.principalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosBuiltInDataContributorRoleDefinitionId}'
    scope: cosmosAccount.id
  }
}

resource communicationAgentCosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, communicationAgentIdentity.name, cosmosBuiltInDataContributorRoleDefinitionId)
  properties: {
    principalId: communicationAgentIdentity.properties.principalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosBuiltInDataContributorRoleDefinitionId}'
    scope: cosmosAccount.id
  }
}

resource hitlWebformCosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, hitlWebformIdentity.name, cosmosBuiltInDataContributorRoleDefinitionId)
  properties: {
    principalId: hitlWebformIdentity.properties.principalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosBuiltInDataContributorRoleDefinitionId}'
    scope: cosmosAccount.id
  }
}

resource flow0WorkerCosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, flow0WorkerIdentity.name, cosmosBuiltInDataContributorRoleDefinitionId)
  properties: {
    principalId: flow0WorkerIdentity.properties.principalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosBuiltInDataContributorRoleDefinitionId}'
    scope: cosmosAccount.id
  }
}

resource agenticOrchestratorServiceBusSenderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(serviceBusNamespace.id, agenticOrchestratorIdentity.name, serviceBusDataSenderRoleDefinitionId)
  scope: serviceBusNamespace
  properties: {
    principalId: agenticOrchestratorIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataSenderRoleDefinitionId
  }
}

resource agenticOrchestratorServiceBusReceiverRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(serviceBusNamespace.id, agenticOrchestratorIdentity.name, serviceBusDataReceiverRoleDefinitionId)
  scope: serviceBusNamespace
  properties: {
    principalId: agenticOrchestratorIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataReceiverRoleDefinitionId
  }
}

resource communicationAgentServiceBusSenderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(serviceBusNamespace.id, communicationAgentIdentity.name, serviceBusDataSenderRoleDefinitionId)
  scope: serviceBusNamespace
  properties: {
    principalId: communicationAgentIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataSenderRoleDefinitionId
  }
}

resource hitlWebformServiceBusSenderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(serviceBusNamespace.id, hitlWebformIdentity.name, serviceBusDataSenderRoleDefinitionId)
  scope: serviceBusNamespace
  properties: {
    principalId: hitlWebformIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataSenderRoleDefinitionId
  }
}

resource flow0WorkerServiceBusSenderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(serviceBusNamespace.id, flow0WorkerIdentity.name, serviceBusDataSenderRoleDefinitionId)
  scope: serviceBusNamespace
  properties: {
    principalId: flow0WorkerIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataSenderRoleDefinitionId
  }
}

resource agenticOrchestratorBlobReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, agenticOrchestratorIdentity.name, storageBlobDataReaderRoleDefinitionId)
  scope: storageAccount
  properties: {
    principalId: agenticOrchestratorIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataReaderRoleDefinitionId
  }
}

resource flow0WorkerBlobReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, flow0WorkerIdentity.name, storageBlobDataReaderRoleDefinitionId)
  scope: storageAccount
  properties: {
    principalId: flow0WorkerIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataReaderRoleDefinitionId
  }
}

resource agenticOrchestratorKeyVaultSecretsUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, agenticOrchestratorIdentity.name, keyVaultSecretsUserRoleDefinitionId)
  scope: keyVault
  properties: {
    principalId: agenticOrchestratorIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

resource communicationAgentKeyVaultSecretsUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, communicationAgentIdentity.name, keyVaultSecretsUserRoleDefinitionId)
  scope: keyVault
  properties: {
    principalId: communicationAgentIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

resource hitlWebformKeyVaultSecretsUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, hitlWebformIdentity.name, keyVaultSecretsUserRoleDefinitionId)
  scope: keyVault
  properties: {
    principalId: hitlWebformIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

resource flow0WorkerKeyVaultSecretsUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, flow0WorkerIdentity.name, keyVaultSecretsUserRoleDefinitionId)
  scope: keyVault
  properties: {
    principalId: flow0WorkerIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

resource communicationAgentCommunicationServicesContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(communicationService.id, communicationAgentIdentity.name, communicationServicesContributorRoleDefinitionId)
  scope: communicationService
  properties: {
    principalId: communicationAgentIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: communicationServicesContributorRoleDefinitionId
  }
}

output identities object = {
  agenticOrchestrator: {
    name: agenticOrchestratorIdentity.name
    clientId: agenticOrchestratorIdentity.properties.clientId
    principalId: agenticOrchestratorIdentity.properties.principalId
    resourceId: agenticOrchestratorIdentity.id
  }
  communicationAgent: {
    name: communicationAgentIdentity.name
    clientId: communicationAgentIdentity.properties.clientId
    principalId: communicationAgentIdentity.properties.principalId
    resourceId: communicationAgentIdentity.id
  }
  hitlWebform: {
    name: hitlWebformIdentity.name
    clientId: hitlWebformIdentity.properties.clientId
    principalId: hitlWebformIdentity.properties.principalId
    resourceId: hitlWebformIdentity.id
  }
  flow0Worker: {
    name: flow0WorkerIdentity.name
    clientId: flow0WorkerIdentity.properties.clientId
    principalId: flow0WorkerIdentity.properties.principalId
    resourceId: flow0WorkerIdentity.id
  }
}
