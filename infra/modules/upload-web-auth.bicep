targetScope = 'resourceGroup'

@description('Container App name for upload-web.')
param containerAppName string

@description('Microsoft Entra tenant id used by Easy Auth.')
param tenantId string

@description('Microsoft Entra application client id used by upload-web Easy Auth.')
param clientId string

@description('Optional audiences accepted by upload-web Easy Auth. Defaults to api://{clientId}.')
param allowedAudiences array = []

@description('Optional Microsoft Entra group object ids allowed to access upload-web.')
param allowedGroupObjectIds array = []

var resolvedAllowedAudiences = empty(allowedAudiences) ? [
  'api://${clientId}'
] : allowedAudiences
var aadValidation = empty(allowedGroupObjectIds)
  ? {
      allowedAudiences: resolvedAllowedAudiences
    }
  : {
      allowedAudiences: resolvedAllowedAudiences
      defaultAuthorizationPolicy: {
        allowedPrincipals: {
          groups: allowedGroupObjectIds
        }
      }
      jwtClaimChecks: {
        allowedGroups: allowedGroupObjectIds
      }
    }

resource uploadWebApp 'Microsoft.App/containerApps@2025-01-01' existing = {
  name: containerAppName
}

resource uploadWebAuth 'Microsoft.App/containerApps/authConfigs@2025-01-01' = {
  parent: uploadWebApp
  name: 'current'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      redirectToProvider: 'azureActiveDirectory'
      unauthenticatedClientAction: 'RedirectToLoginPage'
    }
    httpSettings: {
      requireHttps: true
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        login: {
          loginParameters: [
            'scope=openid profile email'
          ]
        }
        registration: {
          clientId: clientId
          openIdIssuer: '${environment().authentication.loginEndpoint}${tenantId}/v2.0'
        }
        validation: aadValidation
      }
    }
    login: {
      tokenStore: {
        enabled: true
      }
    }
  }
}

@description('Easy Auth config resource id for upload-web.')
output authConfigId string = uploadWebAuth.id
