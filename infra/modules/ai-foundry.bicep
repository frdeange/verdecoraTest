targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for Azure AI Foundry resources.')
param location string

@description('Storage account resource id used for the AI Foundry storage connection.')
param storageAccountId string

@description('Storage account name used for the AI Foundry storage connection.')
param storageAccountName string

@description('Application Insights resource id used for the AI Foundry monitoring connection.')
param applicationInsightsId string

@description('Application Insights instrumentation key used by the AI Foundry monitoring connection.')
@secure()
param applicationInsightsInstrumentationKey string

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  'managed-by': 'bicep'
}

var aiServicesName = 'verdecora-ais-${environment}'
var projectName = 'verdecora-project-${environment}'

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-10-01-preview' = {
  name: aiServicesName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: aiServicesName
    publicNetworkAccess: 'Disabled'
    disableLocalAuth: true
    allowProjectManagement: true
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
      virtualNetworkRules: []
      ipRules: []
    }
  }
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-10-01-preview' = {
  parent: aiServices
  name: projectName
  location: location
  dependsOn: [
    appInsightsConnection
  ]
  #disable-next-line BCP187
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'Verdecora Albaranes AI Project'
    description: 'Verdecora Albaranes AI Project'
  }
}

resource gpt5Deployment 'Microsoft.CognitiveServices/accounts/deployments@2025-10-01-preview' = {
  parent: aiServices
  name: 'gpt-5'
  sku: {
    name: 'GlobalStandard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5'
      version: '2025-08-07'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

resource gpt5MiniDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-10-01-preview' = {
  parent: aiServices
  name: 'gpt-5-mini'
  dependsOn: [
    gpt5Deployment
  ]
  sku: {
    name: 'GlobalStandard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5-mini'
      version: '2025-08-07'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

resource storageConnection 'Microsoft.CognitiveServices/accounts/connections@2025-10-01-preview' = {
  parent: aiServices
  name: '${storageAccountName}-connection'
  dependsOn: [
    gpt5MiniDeployment
  ]
  properties: {
    authType: 'AAD'
    category: 'AzureStorageAccount'
    target: 'https://${storageAccountName}.blob.${az.environment().suffixes.storage}/'
    useWorkspaceManagedIdentity: false
    isSharedToAll: true
    sharedUserList: []
    peRequirement: 'NotRequired'
    peStatus: 'NotApplicable'
    metadata: {
      ApiType: 'Azure'
      ResourceId: storageAccountId
      location: location
    }
  }
}

resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/connections@2025-10-01-preview' = {
  parent: aiServices
  name: 'appinsights-connection'
  dependsOn: [
    storageConnection
  ]
  properties: {
    authType: 'ApiKey'
    category: 'AppInsights'
    target: applicationInsightsId
    credentials: {
      key: applicationInsightsInstrumentationKey
    }
    useWorkspaceManagedIdentity: false
    isSharedToAll: true
    sharedUserList: []
    peRequirement: 'NotRequired'
    peStatus: 'NotApplicable'
    metadata: {
      ApiType: 'Azure'
      ResourceId: applicationInsightsId
    }
  }
}

@description('AI Services account id.')
output aiServicesId string = aiServices.id

@description('AI Services account name.')
output aiServicesName string = aiServices.name

@description('AI Services endpoint.')
output aiServicesEndpoint string = 'https://${aiServicesName}.services.ai.azure.com/'

@description('AI Project endpoint.')
output aiProjectEndpoint string = 'https://${aiServicesName}.services.ai.azure.com/api/projects/${projectName}'

@description('AI Services system-assigned managed identity principal id.')
output aiServicesPrincipalId string = aiServices.identity.principalId

@description('GPT-5 deployment name.')
output gpt5DeploymentName string = gpt5Deployment.name

@description('GPT-5 mini deployment name.')
output gpt5MiniDeploymentName string = gpt5MiniDeployment.name
