targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for the NAT gateway resources.')
param location string

@description('Subnet id associated with the Container Apps environment.')
param subnetId string

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  'managed-by': 'bicep'
}

var subnetSegments = split(subnetId, '/')
var virtualNetworkName = subnetSegments[8]
var subnetName = subnetSegments[10]
var existingSubnet = reference(subnetId, '2023-04-01', 'Full')

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

resource acaSubnetWithNat 'Microsoft.Network/virtualNetworks/subnets@2023-04-01' = {
  name: '${virtualNetworkName}/${subnetName}'
  properties: union(existingSubnet.properties, {
    natGateway: {
      id: natGateway.id
    }
  })
}

@description('NAT gateway id.')
output natGatewayId string = natGateway.id

@description('Controlled egress public IP id.')
output publicIpId string = natGatewayPublicIp.id
