targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for monitoring resources.')
param location string

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  'managed-by': 'bicep'
}

var workspaceName = 'log-albaranes-${environment}'
var appInsightsName = 'appi-albaranes-${environment}'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: workspaceName
  location: location
  tags: tags
  properties: {
    publicNetworkAccessForIngestion: 'Disabled'
    publicNetworkAccessForQuery: 'Disabled'
  }
  sku: {
    name: 'PerGB2018'
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    disableLocalAuth: true
    publicNetworkAccessForIngestion: 'Disabled'
    publicNetworkAccessForQuery: 'Disabled'
  }
}

@description('Log Analytics workspace id.')
output logAnalyticsWorkspaceId string = logAnalytics.id

@description('Application Insights id.')
output applicationInsightsId string = appInsights.id

@description('Application Insights connection string.')
output applicationInsightsConnectionString string = appInsights.properties.ConnectionString

@description('Application Insights instrumentation key.')
output applicationInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey
