targetScope = 'subscription'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for all resources.')
param location string = 'swedencentral'

var resourceGroupName = 'rg-verdecoratest-${environment}'

module resourceGroup './resource-group.bicep' = {
  name: 'resourceGroup'
  params: {
    environment: environment
    location: location
    resourceGroupName: resourceGroupName
  }
}

module network './network.bicep' = {
  name: 'network'
  scope: resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    resourceGroup
  ]
}

module serviceBus './servicebus.bicep' = {
  name: 'serviceBus'
  scope: resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    resourceGroup
  ]
}

module cosmos './cosmos.bicep' = {
  name: 'cosmos'
  scope: resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    resourceGroup
  ]
}

module storage './storage.bicep' = {
  name: 'storage'
  scope: resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    resourceGroup
  ]
}

module keyVault './keyvault.bicep' = {
  name: 'keyVault'
  scope: resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    resourceGroup
  ]
}

module monitoring './monitoring.bicep' = {
  name: 'monitoring'
  scope: resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    resourceGroup
  ]
}

@description('Resource group id.')
output resourceGroupId string = resourceGroup.outputs.resourceGroupId

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
