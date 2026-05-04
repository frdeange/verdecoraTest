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

@description('Resource group id.')
output resourceGroupId string = rg.outputs.resourceGroupId

@description('Virtual network id.')
output virtualNetworkId string = network.outputs.virtualNetworkId

@description('Service Bus namespace id.')
output serviceBusNamespaceId string = serviceBus.outputs.serviceBusNamespaceId

@description('Cosmos DB account id.')
output cosmosAccountId string = cosmos.outputs.cosmosAccountId

@description('Storage account id.')
output storageAccountId string = storage.outputs.storageAccountId

@description('Key Vault id.')
output keyVaultId string = keyVault.outputs.keyVaultId

@description('Log Analytics workspace id.')
output logAnalyticsWorkspaceId string = monitoring.outputs.logAnalyticsWorkspaceId

@description('Application Insights id.')
output applicationInsightsId string = monitoring.outputs.applicationInsightsId

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
