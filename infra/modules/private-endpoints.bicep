targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for private endpoint resources.')
param location string

@description('Virtual network id used for private DNS links.')
param virtualNetworkId string

@description('Subnet id dedicated to private endpoints.')
param subnetId string

@description('Storage account resource id.')
param storageResourceId string = ''

@description('Cosmos DB account resource id.')
param cosmosResourceId string = ''

@description('Key Vault resource id.')
param keyVaultResourceId string = ''

@description('Service Bus namespace resource id.')
param serviceBusResourceId string = ''

@description('Azure AI Foundry resource id.')
param aiServicesResourceId string = ''

@description('Document Intelligence resource id.')
param documentIntelligenceResourceId string = ''

@description('Azure Communication Services resource id.')
param acsResourceId string = ''

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  'managed-by': 'bicep'
}

var vnetSegments = split(virtualNetworkId, '/')
var virtualNetworkName = vnetSegments[8]
var subnetSegments = split(subnetId, '/')
var subnetName = subnetSegments[10]
var privateEndpointSubnetResourceId = subnetId

resource vnet 'Microsoft.Network/virtualNetworks@2023-04-01' existing = {
  name: virtualNetworkName
}

resource storageDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = if (!empty(storageResourceId)) {
  name: 'privatelink.blob.core.windows.net'
  location: 'global'
  tags: tags
}

resource cosmosDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = if (!empty(cosmosResourceId)) {
  name: 'privatelink.documents.azure.com'
  location: 'global'
  tags: tags
}

resource keyVaultDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = if (!empty(keyVaultResourceId)) {
  name: 'privatelink.vaultcore.azure.net'
  location: 'global'
  tags: tags
}

resource serviceBusDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = if (!empty(serviceBusResourceId)) {
  name: 'privatelink.servicebus.windows.net'
  location: 'global'
  tags: tags
}

resource cognitiveServicesDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = if (!empty(aiServicesResourceId) || !empty(documentIntelligenceResourceId)) {
  name: 'privatelink.cognitiveservices.azure.com'
  location: 'global'
  tags: tags
}

// Note: ACS (Communication Services) does NOT support Private Endpoints.
// Access to ACS is controlled via Managed Identity RBAC only.

resource storageDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = if (!empty(storageResourceId)) {
  name: '${storageDnsZone.name}/${virtualNetworkName}-link'
  location: 'global'
  properties: {
    virtualNetwork: {
      id: vnet.id
    }
    registrationEnabled: false
  }
}

resource cosmosDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = if (!empty(cosmosResourceId)) {
  name: '${cosmosDnsZone.name}/${virtualNetworkName}-link'
  location: 'global'
  properties: {
    virtualNetwork: {
      id: vnet.id
    }
    registrationEnabled: false
  }
}

resource keyVaultDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = if (!empty(keyVaultResourceId)) {
  name: '${keyVaultDnsZone.name}/${virtualNetworkName}-link'
  location: 'global'
  properties: {
    virtualNetwork: {
      id: vnet.id
    }
    registrationEnabled: false
  }
}

resource serviceBusDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = if (!empty(serviceBusResourceId)) {
  name: '${serviceBusDnsZone.name}/${virtualNetworkName}-link'
  location: 'global'
  properties: {
    virtualNetwork: {
      id: vnet.id
    }
    registrationEnabled: false
  }
}

resource cognitiveServicesDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = if (!empty(aiServicesResourceId) || !empty(documentIntelligenceResourceId)) {
  name: '${cognitiveServicesDnsZone.name}/${virtualNetworkName}-link'
  location: 'global'
  properties: {
    virtualNetwork: {
      id: vnet.id
    }
    registrationEnabled: false
  }
}

resource storagePrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-04-01' = if (!empty(storageResourceId)) {
  name: 'pe-storage-${environment}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetResourceId
    }
    privateLinkServiceConnections: [
      {
        name: 'storage-blob'
        properties: {
          privateLinkServiceId: storageResourceId
          groupIds: [
            'blob'
          ]
        }
      }
    ]
  }
}

resource storageDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-04-01' = if (!empty(storageResourceId)) {
  parent: storagePrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'storage-blob'
        properties: {
          privateDnsZoneId: storageDnsZone.id
        }
      }
    ]
  }
}

resource cosmosPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-04-01' = if (!empty(cosmosResourceId)) {
  name: 'pe-cosmos-${environment}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetResourceId
    }
    privateLinkServiceConnections: [
      {
        name: 'cosmos-sql'
        properties: {
          privateLinkServiceId: cosmosResourceId
          groupIds: [
            'Sql'
          ]
        }
      }
    ]
  }
}

resource cosmosDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-04-01' = if (!empty(cosmosResourceId)) {
  parent: cosmosPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'cosmos-sql'
        properties: {
          privateDnsZoneId: cosmosDnsZone.id
        }
      }
    ]
  }
}

resource keyVaultPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-04-01' = if (!empty(keyVaultResourceId)) {
  name: 'pe-keyvault-${environment}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetResourceId
    }
    privateLinkServiceConnections: [
      {
        name: 'keyvault-vault'
        properties: {
          privateLinkServiceId: keyVaultResourceId
          groupIds: [
            'vault'
          ]
        }
      }
    ]
  }
}

resource keyVaultDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-04-01' = if (!empty(keyVaultResourceId)) {
  parent: keyVaultPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'keyvault-vault'
        properties: {
          privateDnsZoneId: keyVaultDnsZone.id
        }
      }
    ]
  }
}

resource serviceBusPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-04-01' = if (!empty(serviceBusResourceId)) {
  name: 'pe-servicebus-${environment}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetResourceId
    }
    privateLinkServiceConnections: [
      {
        name: 'servicebus-namespace'
        properties: {
          privateLinkServiceId: serviceBusResourceId
          groupIds: [
            'namespace'
          ]
        }
      }
    ]
  }
}

resource serviceBusDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-04-01' = if (!empty(serviceBusResourceId)) {
  parent: serviceBusPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'servicebus-namespace'
        properties: {
          privateDnsZoneId: serviceBusDnsZone.id
        }
      }
    ]
  }
}

resource aiServicesPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-04-01' = if (!empty(aiServicesResourceId)) {
  name: 'pe-aiservices-${environment}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetResourceId
    }
    privateLinkServiceConnections: [
      {
        name: 'ai-services-account'
        properties: {
          privateLinkServiceId: aiServicesResourceId
          groupIds: [
            'account'
          ]
        }
      }
    ]
  }
}

resource aiServicesDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-04-01' = if (!empty(aiServicesResourceId)) {
  parent: aiServicesPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'ai-services-account'
        properties: {
          privateDnsZoneId: cognitiveServicesDnsZone.id
        }
      }
    ]
  }
}

resource documentIntelligencePrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-04-01' = if (!empty(documentIntelligenceResourceId)) {
  name: 'pe-docintell-${environment}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetResourceId
    }
    privateLinkServiceConnections: [
      {
        name: 'docintell-account'
        properties: {
          privateLinkServiceId: documentIntelligenceResourceId
          groupIds: [
            'account'
          ]
        }
      }
    ]
  }
}

resource documentIntelligenceDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-04-01' = if (!empty(documentIntelligenceResourceId)) {
  parent: documentIntelligencePrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'docintell-account'
        properties: {
          privateDnsZoneId: cognitiveServicesDnsZone.id
        }
      }
    ]
  }
}

@description('Private endpoint subnet name.')
output subnetName string = subnetName
