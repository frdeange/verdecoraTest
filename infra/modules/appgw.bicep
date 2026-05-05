targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for networking resources.')
param location string

@description('Dedicated subnet resource ID for Application Gateway.')
param subnetId string

@description('Internal ACA FQDN used as the backend target for upload-web.')
param backendFqdn string

@description('Existing Key Vault name that stores the Application Gateway TLS certificate secret.')
param keyVaultName string

@secure()
@description('Key Vault secret identifier for the frontend TLS certificate (PFX secret, versionless URI recommended).')
param frontendSslCertificateSecretId string

@description('Public DNS label assigned to the Application Gateway public IP.')
param publicIpDnsLabel string = 'verdecora-upload-${environment}'

@description('Application Gateway resource name.')
param appGatewayName string = 'agw-verdecora-upload-${environment}'

@description('Public IP resource name for the Application Gateway frontend.')
param publicIpName string = 'pip-verdecora-upload-${environment}'

@description('User-assigned managed identity name used by Application Gateway to read TLS material from Key Vault.')
param appGatewayIdentityName string = 'id-appgw-verdecora-upload-${environment}'

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  service: 'upload-web-edge'
  'managed-by': 'bicep'
}
var keyVaultSecretsUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
var frontendPortHttpId = resourceId('Microsoft.Network/applicationGateways/frontendPorts', appGatewayName, 'port-http')
var frontendPortHttpsId = resourceId('Microsoft.Network/applicationGateways/frontendPorts', appGatewayName, 'port-https')
var frontendIpConfigurationId = resourceId('Microsoft.Network/applicationGateways/frontendIPConfigurations', appGatewayName, 'frontend-public')
var backendAddressPoolId = resourceId('Microsoft.Network/applicationGateways/backendAddressPools', appGatewayName, 'upload-web-backend')
var backendHttpSettingsId = resourceId('Microsoft.Network/applicationGateways/backendHttpSettingsCollection', appGatewayName, 'upload-web-https-settings')
var httpsProbeId = resourceId('Microsoft.Network/applicationGateways/probes', appGatewayName, 'upload-web-healthz')
var httpListenerId = resourceId('Microsoft.Network/applicationGateways/httpListeners', appGatewayName, 'listener-http')
var httpsListenerId = resourceId('Microsoft.Network/applicationGateways/httpListeners', appGatewayName, 'listener-https')
var sslCertificateId = resourceId('Microsoft.Network/applicationGateways/sslCertificates', appGatewayName, 'frontend-cert')
var httpRedirectId = resourceId('Microsoft.Network/applicationGateways/redirectConfigurations', appGatewayName, 'http-to-https')

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource appGatewayIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: appGatewayIdentityName
  location: location
  tags: tags
}

resource keyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, appGatewayIdentity.name, keyVaultSecretsUserRoleDefinitionId)
  scope: keyVault
  properties: {
    principalId: appGatewayIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

resource publicIp 'Microsoft.Network/publicIPAddresses@2024-07-01' = {
  name: publicIpName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Regional'
  }
  zones: [
    '1'
    '2'
    '3'
  ]
  properties: {
    publicIPAddressVersion: 'IPv4'
    publicIPAllocationMethod: 'Static'
    dnsSettings: {
      domainNameLabel: toLower(publicIpDnsLabel)
    }
  }
}

resource appGateway 'Microsoft.Network/applicationGateways@2024-07-01' = {
  name: appGatewayName
  location: location
  tags: tags
  zones: [
    '1'
    '2'
    '3'
  ]
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${appGatewayIdentity.id}': {}
    }
  }
  properties: {
    sku: {
      name: 'Standard_v2'
      tier: 'Standard_v2'
    }
    autoscaleConfiguration: {
      minCapacity: 0
      maxCapacity: 10
    }
    enableHttp2: true
    sslPolicy: {
      policyType: 'Predefined'
      policyName: 'AppGwSslPolicy20220101'
    }
    gatewayIPConfigurations: [
      {
        name: 'gateway-ip-config'
        properties: {
          subnet: {
            id: subnetId
          }
        }
      }
    ]
    frontendIPConfigurations: [
      {
        name: 'frontend-public'
        properties: {
          publicIPAddress: {
            id: publicIp.id
          }
        }
      }
    ]
    frontendPorts: [
      {
        name: 'port-http'
        properties: {
          port: 80
        }
      }
      {
        name: 'port-https'
        properties: {
          port: 443
        }
      }
    ]
    backendAddressPools: [
      {
        name: 'upload-web-backend'
        properties: {
          backendAddresses: [
            {
              fqdn: backendFqdn
            }
          ]
        }
      }
    ]
    backendHttpSettingsCollection: [
      {
        name: 'upload-web-https-settings'
        properties: {
          cookieBasedAffinity: 'Disabled'
          pickHostNameFromBackendAddress: true
          port: 443
          protocol: 'Https'
          probe: {
            id: httpsProbeId
          }
          probeEnabled: true
          requestTimeout: 30
        }
      }
    ]
    probes: [
      {
        name: 'upload-web-healthz'
        properties: {
          protocol: 'Https'
          path: '/healthz'
          interval: 30
          timeout: 10
          unhealthyThreshold: 3
          pickHostNameFromBackendHttpSettings: true
          match: {
            statusCodes: [
              '200'
            ]
          }
        }
      }
    ]
    sslCertificates: [
      {
        name: 'frontend-cert'
        properties: {
          keyVaultSecretId: frontendSslCertificateSecretId
        }
      }
    ]
    httpListeners: [
      {
        name: 'listener-http'
        properties: {
          frontendIPConfiguration: {
            id: frontendIpConfigurationId
          }
          frontendPort: {
            id: frontendPortHttpId
          }
          protocol: 'Http'
        }
      }
      {
        name: 'listener-https'
        properties: {
          frontendIPConfiguration: {
            id: frontendIpConfigurationId
          }
          frontendPort: {
            id: frontendPortHttpsId
          }
          protocol: 'Https'
          sslCertificate: {
            id: sslCertificateId
          }
        }
      }
    ]
    redirectConfigurations: [
      {
        name: 'http-to-https'
        properties: {
          includePath: true
          includeQueryString: true
          redirectType: 'Permanent'
          targetListener: {
            id: httpsListenerId
          }
        }
      }
    ]
    requestRoutingRules: [
      {
        name: 'http-redirect'
        properties: {
          httpListener: {
            id: httpListenerId
          }
          redirectConfiguration: {
            id: httpRedirectId
          }
          priority: 100
          ruleType: 'Basic'
        }
      }
      {
        name: 'https-backend'
        properties: {
          backendAddressPool: {
            id: backendAddressPoolId
          }
          backendHttpSettings: {
            id: backendHttpSettingsId
          }
          httpListener: {
            id: httpsListenerId
          }
          priority: 110
          ruleType: 'Basic'
        }
      }
    ]
  }
  dependsOn: [
    keyVaultSecretsUser
  ]
}

@description('Application Gateway public FQDN.')
output appGwPublicFqdn string = publicIp.properties.dnsSettings.fqdn

@description('Application Gateway public IP resource id.')
output appGwPublicIpId string = publicIp.id
