targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for Storage resources.')
param location string

@description('Exact origins allowed to call Blob service CORS. Pass the Front Door/custom-domain origins explicitly because the default azurefd.net hostname is generated at deploy time.')
param blobCorsAllowedOrigins array = []

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  'managed-by': 'bicep'
}

var storageBaseName = 'st-albaranes-${environment}'
var storageAccountName = toLower(replace(storageBaseName, '-', ''))

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_ZRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Disabled'
    supportsHttpsTrafficOnly: true
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  name: '${storageAccount.name}/default'
  properties: {
    isVersioningEnabled: true
    cors: {
      corsRules: length(blobCorsAllowedOrigins) == 0 ? [] : [
        {
          allowedOrigins: blobCorsAllowedOrigins
          allowedMethods: [
            'PUT'
          ]
          allowedHeaders: [
            '*'
          ]
          exposedHeaders: [
            'ETag'
            'x-ms-request-id'
            'x-ms-version'
          ]
          maxAgeInSeconds: 3600
        }
      ]
    }
  }
}

resource albaranesRawContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/albaranes-raw'
  properties: {
    publicAccess: 'None'
    immutableStorageWithVersioning: {
      enabled: false
    }
    immutabilityPolicy: {
      immutabilityPeriodSinceCreationInDays: 30
      state: 'Unlocked'
    }
  }
}

resource albaranesProcessedContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/albaranes-processed'
  properties: {
    publicAccess: 'None'
  }
}

resource dlqContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/dlq'
  properties: {
    publicAccess: 'None'
  }
}

resource lifecyclePolicy 'Microsoft.Storage/storageAccounts/managementPolicies@2023-01-01' = {
  name: '${storageAccount.name}/default'
  properties: {
    policy: {
      rules: [
        {
          name: 'tiering'
          enabled: true
          type: 'Lifecycle'
          definition: {
            actions: {
              baseBlob: {
                tierToCool: {
                  daysAfterModificationGreaterThan: 30
                }
              }
            }
            filters: {
              blobTypes: [
                'blockBlob'
              ]
            }
          }
        }
      ]
    }
  }
}

@description('Storage account id.')
output storageAccountId string = storageAccount.id

@description('Storage account name.')
output storageAccountName string = storageAccount.name

@description('Raw container id.')
output albaranesRawContainerId string = albaranesRawContainer.id

@description('Processed container id.')
output albaranesProcessedContainerId string = albaranesProcessedContainer.id

@description('DLQ container id.')
output dlqContainerId string = dlqContainer.id
