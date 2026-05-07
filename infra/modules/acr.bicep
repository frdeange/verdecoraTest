targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for Container Registry resources.')
param location string

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'acralbaranes${environment}'
  location: location
  sku: {
    name: 'Standard'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
    dataEndpointEnabled: false
  }
}

@description('Azure Container Registry resource id.')
output acrId string = acr.id

@description('Azure Container Registry name.')
output acrName string = acr.name

@description('Azure Container Registry login server.')
output acrLoginServer string = acr.properties.loginServer
