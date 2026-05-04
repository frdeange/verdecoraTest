targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for the NAT gateway resources.')
param location string

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  'managed-by': 'bicep'
}

resource natGatewayPublicIp 'Microsoft.Network/publicIPAddresses@2023-04-01' = {
  name: 'pip-nat-albaranes-${environment}'
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAddressVersion: 'IPv4'
    publicIPAllocationMethod: 'Static'
    idleTimeoutInMinutes: 10
  }
}

resource natGateway 'Microsoft.Network/natGateways@2023-04-01' = {
  name: 'nat-albaranes-${environment}'
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    idleTimeoutInMinutes: 10
    publicIpAddresses: [
      {
        id: natGatewayPublicIp.id
      }
    ]
  }
}

// Note: NAT Gateway <-> Subnet association is handled in network.bicep
// to avoid circular dependencies with Container Apps.

@description('NAT gateway id.')
output natGatewayId string = natGateway.id

@description('Controlled egress public IP id.')
output publicIpId string = natGatewayPublicIp.id
