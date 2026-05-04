targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for Container Registry resources.')
param location string

@description('Optional subnet resource id used by the ACR dedicated build agent pool.')
param agentPoolSubnetId string = ''

@description('Name of the dedicated ACR build agent pool.')
param agentPoolName string = 'buildpool-${environment}'

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'acralbaranes${environment}'
  location: location
  sku: {
    name: 'Premium'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Disabled'
    networkRuleBypassOptions: 'AzureServices'
    dataEndpointEnabled: false
  }
}

resource agentPool 'Microsoft.ContainerRegistry/registries/agentPools@2025-03-01-preview' = if (!empty(agentPoolSubnetId)) {
  parent: acr
  name: agentPoolName
  location: location
  properties: {
    count: 1
    os: 'Linux'
    tier: 'S2'
    virtualNetworkSubnetResourceId: agentPoolSubnetId
  }
}

@description('Azure Container Registry resource id.')
output acrId string = acr.id

@description('Azure Container Registry name.')
output acrName string = acr.name

@description('Azure Container Registry login server.')
output acrLoginServer string = acr.properties.loginServer

@description('Dedicated ACR build agent pool name.')
output agentPoolName string = !empty(agentPoolSubnetId) ? agentPool.name : ''
