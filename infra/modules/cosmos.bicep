targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for Cosmos DB resources.')
param location string

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  'managed-by': 'bicep'
}

var accountName = toLower('cosmos-albaranes-${environment}')

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: accountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    disableLocalAuth: true
    publicNetworkAccess: 'Disabled'
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
  }
}

resource albaranesDb 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  name: '${cosmosAccount.name}/albaranes-db'
  properties: {
    resource: {
      id: 'albaranes-db'
    }
    options: {
      autoscaleSettings: {
        maxThroughput: 10000
      }
    }
  }
}

resource albaranesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  name: '${cosmosAccount.name}/albaranes-db/albaranes'
  properties: {
    resource: {
      id: 'albaranes'
      partitionKey: {
        paths: [
          '/pk'
        ]
        kind: 'Hash'
      }
    }
    options: {}
  }
}

resource tiendasContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  name: '${cosmosAccount.name}/albaranes-db/tiendas'
  properties: {
    resource: {
      id: 'tiendas'
      partitionKey: {
        paths: [
          '/tienda_id'
        ]
        kind: 'Hash'
      }
    }
    options: {}
  }
}

resource dlqContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  name: '${cosmosAccount.name}/albaranes-db/dlq'
  properties: {
    resource: {
      id: 'dlq'
      partitionKey: {
        paths: [
          '/pk'
        ]
        kind: 'Hash'
      }
    }
    options: {}
  }
}

resource uploadSessionsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  name: '${cosmosAccount.name}/albaranes-db/upload-sessions'
  properties: {
    resource: {
      id: 'upload-sessions'
      partitionKey: {
        paths: [
          '/user_oid'
        ]
        kind: 'Hash'
      }
      defaultTtl: 86400
    }
    options: {
      throughput: 400
    }
  }
}

@description('Cosmos DB account id.')
output cosmosAccountId string = cosmosAccount.id

@description('Cosmos DB account name.')
output cosmosAccountName string = cosmosAccount.name

@description('Cosmos DB endpoint.')
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint

@description('Cosmos DB database id.')
output albaranesDatabaseId string = albaranesDb.id

@description('Albaranes container id.')
output albaranesContainerId string = albaranesContainer.id

@description('Tiendas container id.')
output tiendasContainerId string = tiendasContainer.id

@description('DLQ container id.')
output dlqContainerId string = dlqContainer.id

@description('Upload sessions container id.')
output uploadSessionsContainerId string = uploadSessionsContainer.id
