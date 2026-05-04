targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for Azure OpenAI resources.')
param location string

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  'managed-by': 'bicep'
}

var openAiAccountName = 'verdecora-openai-${environment}'
var openAiCustomSubdomainName = 'verdecora-openai-${environment}'

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: openAiAccountName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: openAiCustomSubdomainName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource gpt5Deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAiAccount
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
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

resource gpt5MiniDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAiAccount
  name: 'gpt-5-mini'
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
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

@description('Azure OpenAI account id.')
output openaiAccountId string = openAiAccount.id

@description('Azure OpenAI account name.')
output openaiAccountName string = openAiAccount.name

@description('Azure OpenAI endpoint.')
output openaiEndpoint string = 'https://${openAiCustomSubdomainName}.openai.azure.com/'

@description('Azure OpenAI system-assigned managed identity principal id.')
output openaiPrincipalId string = openAiAccount.identity.principalId
