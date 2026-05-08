targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for networking resources.')
param location string

@description('Address prefix for the virtual network.')
param vnetAddressPrefix string = '10.10.0.0/16'

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  'managed-by': 'bicep'
}

var vnetName = 'vnet-albaranes-${environment}'

resource nsgAca 'Microsoft.Network/networkSecurityGroups@2023-04-01' = {
  name: 'nsg-aca-env-albaranes-${environment}'
  location: location
  tags: tags
}

resource nsgFunctions 'Microsoft.Network/networkSecurityGroups@2023-04-01' = {
  name: 'nsg-functions-albaranes-${environment}'
  location: location
  tags: tags
}

resource nsgPe 'Microsoft.Network/networkSecurityGroups@2023-04-01' = {
  name: 'nsg-pe-albaranes-${environment}'
  location: location
  tags: tags
}

resource nsgRunners 'Microsoft.Network/networkSecurityGroups@2023-04-01' = {
  name: 'nsg-runners-albaranes-${environment}'
  location: location
  tags: tags
}

resource nsgEgress 'Microsoft.Network/networkSecurityGroups@2023-04-01' = {
  name: 'nsg-egress-albaranes-${environment}'
  location: location
  tags: tags
}

resource nsgUploadWeb 'Microsoft.Network/networkSecurityGroups@2023-04-01' = {
  name: 'nsg-upload-web-albaranes-${environment}'
  location: location
  tags: tags
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-04-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    subnets: [
      {
        name: 'snet-aca-env'
        properties: {
          addressPrefix: '10.10.0.0/23'
          networkSecurityGroup: {
            id: nsgAca.id
          }
          delegations: [
            {
              name: 'acaDelegation'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        name: 'snet-functions'
        properties: {
          addressPrefix: '10.10.2.0/27'
          networkSecurityGroup: {
            id: nsgFunctions.id
          }
        }
      }
      {
        name: 'snet-pe'
        properties: {
          addressPrefix: '10.10.3.0/24'
          networkSecurityGroup: {
            id: nsgPe.id
          }
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
      {
        name: 'snet-runners'
        properties: {
          addressPrefix: '10.10.4.0/27'
          networkSecurityGroup: {
            id: nsgRunners.id
          }
          delegations: [
            {
              name: 'acaDelegation'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        name: 'snet-egress'
        properties: {
          addressPrefix: '10.10.5.0/26'
          networkSecurityGroup: {
            id: nsgEgress.id
          }
        }
      }
      {
        name: 'snet-upload-web'
        properties: {
          addressPrefix: '10.10.6.0/23'
          networkSecurityGroup: {
            id: nsgUploadWeb.id
          }
          delegations: [
            {
              name: 'acaDelegation'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
    ]
  }
}

@description('Virtual network id.')
output virtualNetworkId string = vnet.id

@description('ACA environment subnet id.')
output subnetAcaEnvId string = vnet.properties.subnets[0].id

@description('Functions subnet id.')
output subnetFunctionsId string = vnet.properties.subnets[1].id

@description('Private endpoint subnet id.')
output subnetPeId string = vnet.properties.subnets[2].id

@description('Runner subnet id.')
output subnetRunnersId string = vnet.properties.subnets[3].id

@description('Egress subnet id.')
output subnetEgressId string = vnet.properties.subnets[4].id

@description('Upload-web ACA environment subnet id.')
output subnetUploadWebId string = vnet.properties.subnets[5].id

@description('ACA NSG id.')
output nsgAcaId string = nsgAca.id

@description('Functions NSG id.')
output nsgFunctionsId string = nsgFunctions.id

@description('Private endpoint NSG id.')
output nsgPeId string = nsgPe.id

@description('Runners NSG id.')
output nsgRunnersId string = nsgRunners.id

@description('Egress NSG id.')
output nsgEgressId string = nsgEgress.id

@description('Upload-web ACA environment NSG id.')
output nsgUploadWebId string = nsgUploadWeb.id
