targetScope = 'resourceGroup'

@description('Deployment environment name.')
param environment string

@description('Custom domain hostname for the upload web (e.g. upload.verdecora.example.com). Leave empty to use the default Front Door endpoint.')
param customDomainHostname string = ''

@description('Internal FQDN of the upload-web Container App used as the Private Link backend.')
param backendFqdn string

@description('Resource ID of the Container App Environment (for Private Link Service).')
param containerAppEnvironmentId string

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  service: 'upload-web-edge'
  'managed-by': 'bicep'
}

var profileName = 'afd-verdecora-${environment}'
var endpointName = 'upload-web'
var originGroupName = 'upload-web-origins'
var originName = 'aca-upload-web'
var routeName = 'upload-web-route'
var wafPolicyName = 'wafverdecora${environment}'

// 1. WAF Policy (managed rules OWASP 3.2 + bot protection)
resource wafPolicy 'Microsoft.Network/FrontDoorWebApplicationFirewallPolicies@2024-02-01' = {
  name: wafPolicyName
  location: 'global'
  tags: tags
  sku: {
    name: 'Premium_AzureFrontDoor'
  }
  properties: {
    policySettings: {
      enabledState: 'Enabled'
      mode: 'Prevention'
      requestBodyCheck: 'Enabled'
    }
    managedRules: {
      managedRuleSets: [
        {
          ruleSetType: 'Microsoft_DefaultRuleSet'
          ruleSetVersion: '2.1'
          ruleSetAction: 'Block'
        }
        {
          ruleSetType: 'Microsoft_BotManagerRuleSet'
          ruleSetVersion: '1.1'
          ruleSetAction: 'Block'
        }
      ]
    }
  }
}

// 2. Front Door Profile (Premium for Private Link)
resource frontDoorProfile 'Microsoft.Cdn/profiles@2024-09-01' = {
  name: profileName
  location: 'global'
  tags: tags
  sku: {
    name: 'Premium_AzureFrontDoor'
  }
}

// 3. Endpoint
resource endpoint 'Microsoft.Cdn/profiles/afdEndpoints@2024-09-01' = {
  parent: frontDoorProfile
  name: endpointName
  location: 'global'
  tags: tags
  properties: {
    enabledState: 'Enabled'
  }
}

// 4. Origin Group (with health probe)
resource originGroup 'Microsoft.Cdn/profiles/originGroups@2024-09-01' = {
  parent: frontDoorProfile
  name: originGroupName
  properties: {
    loadBalancingSettings: {
      sampleSize: 4
      successfulSamplesRequired: 3
      additionalLatencyInMilliseconds: 50
    }
    healthProbeSettings: {
      probePath: '/healthz'
      probeRequestType: 'GET'
      probeProtocol: 'Https'
      probeIntervalInSeconds: 30
    }
    sessionAffinityState: 'Disabled'
  }
}

// 5. Origin (Private Link to ACA)
resource origin 'Microsoft.Cdn/profiles/originGroups/origins@2024-09-01' = {
  parent: originGroup
  name: originName
  properties: {
    hostName: backendFqdn
    httpPort: 80
    httpsPort: 443
    originHostHeader: backendFqdn
    priority: 1
    weight: 1000
    enabledState: 'Enabled'
    sharedPrivateLinkResource: {
      privateLink: {
        id: containerAppEnvironmentId
      }
      groupId: 'managedEnvironments'
      privateLinkLocation: 'swedencentral'
      requestMessage: 'Front Door Private Link for upload-web'
      status: 'Approved'
    }
    enforceCertificateNameCheck: true
  }
}

// 6. Route
resource route 'Microsoft.Cdn/profiles/afdEndpoints/routes@2024-09-01' = {
  parent: endpoint
  name: routeName
  properties: {
    originGroup: {
      id: originGroup.id
    }
    supportedProtocols: [
      'Http'
      'Https'
    ]
    patternsToMatch: [
      '/*'
    ]
    forwardingProtocol: 'HttpsOnly'
    httpsRedirect: 'Enabled'
    linkToDefaultDomain: 'Enabled'
    cacheConfiguration: null // No caching for dynamic app
  }
  dependsOn: [
    origin // Ensure origin is created before route
  ]
}

// 7. Security Policy (links WAF to endpoint)
resource securityPolicy 'Microsoft.Cdn/profiles/securityPolicies@2024-09-01' = {
  parent: frontDoorProfile
  name: 'upload-web-waf'
  properties: {
    parameters: {
      type: 'WebApplicationFirewall'
      wafPolicy: {
        id: wafPolicy.id
      }
      associations: [
        {
          domains: [
            {
              id: endpoint.id
            }
          ]
          patternsToMatch: [
            '/*'
          ]
        }
      ]
    }
  }
}

// Outputs
output frontDoorEndpointHostname string = endpoint.properties.hostName
output frontDoorProfileId string = frontDoorProfile.id
output wafPolicyId string = wafPolicy.id
