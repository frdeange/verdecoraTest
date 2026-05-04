targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for Azure Communication Services resources.')
param location string

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  region: location
  'managed-by': 'bicep'
}

var communicationServiceName = 'verdecora-acs-${environment}'
var emailServiceName = 'verdecora-email-${environment}'
var azureManagedDomainResourceName = 'AzureManagedDomain'

resource emailService 'Microsoft.Communication/emailServices@2023-04-01' = {
  name: emailServiceName
  location: 'global'
  tags: tags
  properties: {
    dataLocation: 'Europe'
  }
}

resource azureManagedSenderDomain 'Microsoft.Communication/emailServices/domains@2023-04-01' = {
  parent: emailService
  name: azureManagedDomainResourceName
  location: 'global'
  tags: tags
  properties: {
    domainManagement: 'AzureManaged'
    userEngagementTracking: 'Disabled'
  }
}

resource communicationService 'Microsoft.Communication/communicationServices@2026-03-18' = {
  name: communicationServiceName
  location: 'global'
  tags: tags
  properties: {
    dataLocation: 'Europe'
    disableLocalAuth: true
    linkedDomains: [
      azureManagedSenderDomain.id
    ]
    publicNetworkAccess: 'Enabled'
  }
}

/*
resource productionSenderDomain 'Microsoft.Communication/emailServices/domains@2023-04-01' = {
  parent: emailService
  name: 'mail.verdecora.example'
  location: 'global'
  tags: tags
  properties: {
    domainManagement: 'CustomerManaged'
    userEngagementTracking: 'Disabled'
  }
}
*/

@description('Azure Communication Services resource id.')
output acsId string = communicationService.id

@description('Azure Communication Services resource name.')
output acsName string = communicationService.name

@description('Azure Communication Services endpoint.')
output acsEndpoint string = 'https://${communicationService.properties.hostName}'

@description('Resolved sender domain used by ACS email.')
output emailSenderDomain string = azureManagedSenderDomain.properties.fromSenderDomain
