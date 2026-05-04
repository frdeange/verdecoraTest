targetScope = 'subscription'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for all resources.')
param location string = 'swedencentral'

var resourceGroupName = 'rg-verdecoratest-${environment}'

module rg './resource-group.bicep' = {
  name: 'resourceGroup'
  params: {
    environment: environment
    location: location
    resourceGroupName: resourceGroupName
  }
}

module network './network.bicep' = {
  name: 'network'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

module serviceBus './servicebus.bicep' = {
  name: 'serviceBus'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

module cosmos './cosmos.bicep' = {
  name: 'cosmos'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

module storage './storage.bicep' = {
  name: 'storage'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

module keyVault './keyvault.bicep' = {
  name: 'keyVault'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

module monitoring './monitoring.bicep' = {
  name: 'monitoring'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

module openAi './openai.bicep' = {
  name: 'openAi'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

module docIntell './docintell.bicep' = {
  name: 'docIntell'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

module acs './acs.bicep' = {
  name: 'acs'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

module containerApps './container-apps.bicep' = {
  name: 'containerApps'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
    infrastructureSubnetId: network.outputs.subnetAcaEnvId
    logAnalyticsWorkspaceName: 'log-albaranes-${environment}'
    openAiEndpoint: openAi.outputs.openaiEndpoint
    cosmosEndpoint: cosmos.outputs.cosmosEndpoint
    docIntellEndpoint: docIntell.outputs.docIntellEndpoint
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
    serviceBusNamespaceName: serviceBus.outputs.serviceBusNamespaceName
    ingestionQueueName: serviceBus.outputs.ingestionQueueName
    extractionQueueName: serviceBus.outputs.extraccionQueueName
  }
  dependsOn: [
    rg
  ]
}

module eventGrid './eventgrid.bicep' = {
  name: 'eventGrid'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
    storageAccountName: storage.outputs.storageAccountName
    serviceBusNamespaceName: serviceBus.outputs.serviceBusNamespaceName
    queueName: serviceBus.outputs.ingestionQueueName
  }
  dependsOn: [
    rg
  ]
}

module identity './identity.bicep' = {
  name: 'identity'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    location: location
    cosmosAccountName: cosmos.outputs.cosmosAccountName
    serviceBusNamespaceName: serviceBus.outputs.serviceBusNamespaceName
    storageAccountName: storage.outputs.storageAccountName
    keyVaultName: keyVault.outputs.keyVaultName
    communicationServiceName: acs.outputs.acsName
    openAiAccountName: openAi.outputs.openaiAccountName
    docIntellAccountName: docIntell.outputs.docIntellAccountName
    deployUserAssignedIdentities: false
    orchestratorPrincipalId: containerApps.outputs.orchestratorPrincipalId
    hitlWebformPrincipalId: containerApps.outputs.hitlWebformPrincipalId
    flow0WorkerPrincipalId: containerApps.outputs.flow0DedupPrincipalId
  }
  dependsOn: [
    rg
  ]
}

@description('Resource group id.')
output resourceGroupId string = rg.outputs.resourceGroupId

@description('Virtual network id.')
output virtualNetworkId string = network.outputs.virtualNetworkId

@description('Service Bus namespace id.')
output serviceBusNamespaceId string = serviceBus.outputs.serviceBusNamespaceId

@description('Service Bus namespace name.')
output serviceBusNamespaceName string = serviceBus.outputs.serviceBusNamespaceName

@description('Service Bus fully qualified namespace.')
output serviceBusFullyQualifiedNamespace string = serviceBus.outputs.serviceBusFullyQualifiedNamespace

@description('Flow 0 ingestion queue id.')
output ingestionQueueId string = serviceBus.outputs.ingestionQueueId

@description('Extraction queue id.')
output extraccionQueueId string = serviceBus.outputs.extraccionQueueId

@description('Cosmos DB account id.')
output cosmosAccountId string = cosmos.outputs.cosmosAccountId

@description('Cosmos DB endpoint.')
output cosmosEndpoint string = cosmos.outputs.cosmosEndpoint

@description('Storage account id.')
output storageAccountId string = storage.outputs.storageAccountId

@description('Storage account name.')
output storageAccountName string = storage.outputs.storageAccountName

@description('Key Vault id.')
output keyVaultId string = keyVault.outputs.keyVaultId

@description('Log Analytics workspace id.')
output logAnalyticsWorkspaceId string = monitoring.outputs.logAnalyticsWorkspaceId

@description('Application Insights id.')
output applicationInsightsId string = monitoring.outputs.applicationInsightsId

@description('Application Insights connection string.')
output applicationInsightsConnectionString string = monitoring.outputs.applicationInsightsConnectionString

@description('Azure Communication Services resource id.')
output acsId string = acs.outputs.acsId

@description('Azure Communication Services endpoint.')
output acsEndpoint string = acs.outputs.acsEndpoint

@description('Azure-managed sender domain for HITL email.')
output emailSenderDomain string = acs.outputs.emailSenderDomain

@description('Azure OpenAI account id.')
output openaiAccountId string = openAi.outputs.openaiAccountId

@description('Azure OpenAI endpoint.')
output openaiEndpoint string = openAi.outputs.openaiEndpoint

@description('Azure OpenAI principal id.')
output openaiPrincipalId string = openAi.outputs.openaiPrincipalId

@description('Document Intelligence account id.')
output docIntellId string = docIntell.outputs.docIntellId

@description('Document Intelligence endpoint.')
output docIntellEndpoint string = docIntell.outputs.docIntellEndpoint

@description('Container Apps environment id.')
output containerAppsEnvironmentId string = containerApps.outputs.managedEnvironmentId

@description('Main orchestrator container app id.')
output orchestratorAppId string = containerApps.outputs.orchestratorAppId

@description('Flow 0 dedup ACA Job id.')
output flow0DedupJobId string = containerApps.outputs.flow0DedupJobId

@description('HITL web form container app id.')
output hitlWebformAppId string = containerApps.outputs.hitlWebformAppId

@description('Event Grid system topic id.')
output eventGridSystemTopicId string = eventGrid.outputs.systemTopicId

@description('Event Grid BlobCreated subscription id.')
output eventGridSubscriptionId string = eventGrid.outputs.eventSubscriptionId

@description('Identity assignment summary.')
output workloadIdentities object = identity.outputs.identities
