targetScope = 'subscription'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for the resource group.')
param location string

@description('Resource group name.')
param resourceGroupName string = 'rg-verdecoratest-${environment}'

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  'managed-by': 'bicep'
}

resource resourceGroup 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

@description('Resource group id.')
output resourceGroupId string = resourceGroup.id

@description('Resource group name.')
output resourceGroupOutputName string = resourceGroup.name
