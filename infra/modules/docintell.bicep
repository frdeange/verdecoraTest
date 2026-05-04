targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for Document Intelligence resources.')
param location string

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  'managed-by': 'bicep'
}

var docIntellAccountName = 'verdecora-docintell-${environment}'
var docIntellCustomSubdomainName = 'verdecora-docintell-${environment}'

resource docIntellAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: docIntellAccountName
  location: location
  tags: tags
  kind: 'FormRecognizer'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: docIntellCustomSubdomainName
    disableLocalAuth: true
    publicNetworkAccess: 'Disabled'
  }
}

@description('Document Intelligence account id.')
output docIntellId string = docIntellAccount.id

@description('Document Intelligence account name.')
output docIntellAccountName string = docIntellAccount.name

@description('Document Intelligence endpoint.')
output docIntellEndpoint string = 'https://${docIntellCustomSubdomainName}.cognitiveservices.azure.com/'
