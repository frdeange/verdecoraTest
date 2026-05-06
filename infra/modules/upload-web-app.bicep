targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for Container Apps resources.')
param location string

@description('Existing Container Apps managed environment resource id used by upload-web.')
param managedEnvironmentId string

@description('Azure Container Registry login server used for the upload-web image.')
param acrLoginServer string

@description('Storage account blob endpoint exposed to upload-web.')
param storageAccountUrl string

@description('Cosmos DB endpoint exposed to upload-web.')
param cosmosEndpoint string

@description('Application Insights connection string injected into upload-web.')
param applicationInsightsConnectionString string

@description('Optional override for the upload-web image.')
param uploadWebImage string = ''

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  service: 'upload-web'
  'managed-by': 'bicep'
}
var resolvedUploadWebImage = empty(uploadWebImage) ? '${acrLoginServer}/verdecora-upload-web:latest' : uploadWebImage

resource uploadWebApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'verdecora-upload-web-${environment}'
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: managedEnvironmentId
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      ingress: {
        external: false // Internal — only accessible via Front Door Private Link
        allowInsecure: false
        targetPort: 8000
        transport: 'Auto'
      }
    }
    template: {
      containers: [
        {
          name: 'upload-web'
          image: resolvedUploadWebImage
          env: [
            {
              name: 'STORAGE_ACCOUNT_URL'
              value: storageAccountUrl
            }
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosEndpoint
            }
            {
              name: 'APPINSIGHTS_CONNECTION_STRING'
              value: applicationInsightsConnectionString
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/healthz'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
      }
    }
  }
}

@description('Upload-web container app id.')
output uploadWebAppId string = uploadWebApp.id

@description('Upload-web container app name.')
output uploadWebAppName string = uploadWebApp.name

@description('Upload-web managed identity principal id.')
output uploadWebPrincipalId string = uploadWebApp.identity.principalId
