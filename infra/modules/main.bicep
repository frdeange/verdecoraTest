targetScope = 'subscription'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for all resources.')
param location string = 'swedencentral'

@description('Ops team email notified by Azure Monitor action groups.')
param opsEmailAddress string = 'ops@verdecora.example.com'

@description('Optional override for the orchestrator image during infrastructure deployments.')
param orchestratorImage string = ''

@description('Optional override for the Flow 0 dedup job image during infrastructure deployments.')
param dedupJobImage string = ''

@description('Optional override for the HITL webform image during infrastructure deployments.')
param hitlWebformImage string = ''

@description('Optional override for the escalation timer job image during infrastructure deployments.')
param escalationTimerJobImage string = ''

@description('Optional override for the upload-web image during infrastructure deployments.')
param uploadWebImage string = ''

@description('Enable upload-web Container App deployment.')
param enableUploadWeb bool = false

@description('Microsoft Entra application client id used by upload-web Easy Auth.')
param uploadWebEntraClientId string = ''

@description('Enable Easy Auth deployment for upload-web once the container app exists.')
param enableUploadWebAuth bool = false

@description('Optional audiences accepted by upload-web Easy Auth. Defaults to api://{uploadWebEntraClientId}.')
param uploadWebAllowedAudiences array = []

@description('Optional Microsoft Entra group object ids allowed to access upload-web.')
param uploadWebAllowedGroupObjectIds array = []

@description('Exact origins allowed to call Blob CORS for upload-web browser uploads (for example the Front Door custom domain).')
param uploadWebBlobCorsAllowedOrigins array = []

var resourceGroupName = 'rg-verdecoratest-${environment}'
var storageAccountUrl = 'https://${storage.outputs.storageAccountName}.blob.${az.environment().suffixes.storage}/'

module rg './resource-group.bicep' = {
  name: 'resourceGroup'
  params: {
    environment: environment
    location: location
    resourceGroupName: resourceGroupName
  }
}

module network './network.bicep' = {
  name: 'network'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

module serviceBus './servicebus.bicep' = {
  name: 'serviceBus'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

module cosmos './cosmos.bicep' = {
  name: 'cosmos'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

module storage './storage.bicep' = {
  name: 'storage'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
    blobCorsAllowedOrigins: uploadWebBlobCorsAllowedOrigins
  }
  dependsOn: [
    rg
  ]
}

module acr './acr.bicep' = {
  name: 'acr'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

module keyVault './keyvault.bicep' = {
  name: 'keyVault'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

module monitoring './monitoring.bicep' = {
  name: 'monitoring'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

module aiFoundry './ai-foundry.bicep' = {
  name: 'aiFoundry'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
    storageAccountId: storage.outputs.storageAccountId
    storageAccountName: storage.outputs.storageAccountName
    applicationInsightsId: monitoring.outputs.applicationInsightsId
    applicationInsightsInstrumentationKey: monitoring.outputs.applicationInsightsInstrumentationKey
  }
  dependsOn: [
    rg
  ]
}

module docIntell './docintell.bicep' = {
  name: 'docIntell'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

module acs './acs.bicep' = {
  name: 'acs'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

/*
Network hardening (Private Endpoints + NAT Gateway) is always deployed.
The 'environment' parameter is kept for future dev/prod differentiation
but the current PoC deploys a production-grade setup in all environments.
*/
var enableNetworkHardening = true // Always on — this PoC simulates a real production environment

module natGateway './nat-gateway.bicep' = if (enableNetworkHardening) {
  name: 'natGateway'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    rg
  ]
}

module privateEndpoints './private-endpoints.bicep' = if (enableNetworkHardening) {
  name: 'privateEndpoints'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
    virtualNetworkId: network.outputs.virtualNetworkId
    subnetId: network.outputs.subnetPeId
    storageResourceId: storage.outputs.storageAccountId
    cosmosResourceId: cosmos.outputs.cosmosAccountId
    keyVaultResourceId: keyVault.outputs.keyVaultId
    serviceBusResourceId: serviceBus.outputs.serviceBusNamespaceId
    aiServicesResourceId: aiFoundry.outputs.aiServicesId
    documentIntelligenceResourceId: docIntell.outputs.docIntellId
    // ACS does not support Private Endpoints — secured via MI RBAC only
  }
  dependsOn: [
    rg
  ]
}

module runners './runners.bicep' = {
  name: 'runners'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
    infrastructureSubnetId: network.outputs.subnetRunnersId
    keyVaultName: keyVault.outputs.keyVaultName
    githubPatSecretUri: keyVault.outputs.githubPatSecretUri
    repoUrl: 'https://github.com/frdeange/verdecoraTest'
    runnerImage: '${acr.outputs.acrLoginServer}/github-runner-azure-cli:latest'
    runnerRegistryServer: acr.outputs.acrLoginServer
    acrResourceId: acr.outputs.acrId
    resourceGroupId: rg.outputs.resourceGroupId
  }
  dependsOn: [
    rg
    privateEndpoints
  ]
}

module containerApps './container-apps.bicep' = {
  name: 'containerApps'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
    infrastructureSubnetId: network.outputs.subnetAcaEnvId
    logAnalyticsWorkspaceName: 'log-albaranes-${environment}'
    aiServicesEndpoint: aiFoundry.outputs.aiServicesEndpoint
    cosmosEndpoint: cosmos.outputs.cosmosEndpoint
    docIntellEndpoint: docIntell.outputs.docIntellEndpoint
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
    serviceBusNamespaceName: serviceBus.outputs.serviceBusNamespaceName
    ingestionQueueName: serviceBus.outputs.ingestionQueueName
    extractionQueueName: serviceBus.outputs.extraccionQueueName
    hitlDecisionsTopicName: serviceBus.outputs.hitlDecisionsTopicName
    storageAccountUrl: storageAccountUrl
    acsEndpoint: acs.outputs.acsEndpoint
    keyVaultUrl: keyVault.outputs.keyVaultUri
    tenantId: subscription().tenantId
    acrLoginServer: acr.outputs.acrLoginServer
    orchestratorImage: orchestratorImage
    dedupJobImage: dedupJobImage
    hitlWebformImage: hitlWebformImage
    escalationTimerJobImage: escalationTimerJobImage
  }
  dependsOn: [
    rg
    natGateway
    privateEndpoints
  ]
}

module uploadWebApp './upload-web-app.bicep' = if (enableUploadWeb) {
  name: 'uploadWebApp'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
    infrastructureSubnetId: network.outputs.subnetUploadWebId
    acrLoginServer: acr.outputs.acrLoginServer
    storageAccountUrl: storageAccountUrl
    cosmosEndpoint: cosmos.outputs.cosmosEndpoint
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
    uploadWebImage: uploadWebImage
  }
}

var uploadWebAppName = 'verdecora-upload-web-${environment}'

module frontDoor './frontdoor.bicep' = if (enableUploadWeb) {
  name: 'frontDoor'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    backendFqdn: enableUploadWeb ? uploadWebApp.outputs.uploadWebFqdn : ''
  }
}

module uploadWebAuth './upload-web-auth.bicep' = if (enableUploadWebAuth && !empty(uploadWebEntraClientId)) {
  name: 'uploadWebAuth'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    containerAppName: uploadWebAppName
    tenantId: subscription().tenantId
    clientId: uploadWebEntraClientId
    allowedAudiences: uploadWebAllowedAudiences
    allowedGroupObjectIds: uploadWebAllowedGroupObjectIds
  }
  dependsOn: [
    rg
  ]
}

module eventGrid './eventgrid.bicep' = {
  name: 'eventGrid'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
    storageAccountName: storage.outputs.storageAccountName
    serviceBusNamespaceName: serviceBus.outputs.serviceBusNamespaceName
    queueName: serviceBus.outputs.ingestionQueueName
  }
  dependsOn: [
    rg
  ]
}

module identity './identity.bicep' = {
  name: 'identity'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    cosmosAccountName: cosmos.outputs.cosmosAccountName
    serviceBusNamespaceName: serviceBus.outputs.serviceBusNamespaceName
    storageAccountName: storage.outputs.storageAccountName
    keyVaultName: keyVault.outputs.keyVaultName
    communicationServiceName: acs.outputs.acsName
    aiServicesAccountName: aiFoundry.outputs.aiServicesName
    docIntellAccountName: docIntell.outputs.docIntellAccountName
    acrName: acr.outputs.acrName
    orchestratorPrincipalId: containerApps.outputs.orchestratorPrincipalId
    hitlWebformPrincipalId: containerApps.outputs.hitlWebformPrincipalId
    flow0WorkerPrincipalId: containerApps.outputs.flow0DedupPrincipalId
    escalationTimerPrincipalId: containerApps.outputs.escalationTimerPrincipalId
    uploadWebPrincipalId: enableUploadWeb ? uploadWebApp.outputs.uploadWebPrincipalId : ''
  }
  dependsOn: [
    rg
  ]
}

module alerts './alerts.bicep' = {
  name: 'alerts'
  scope: az.resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
    applicationInsightsId: monitoring.outputs.applicationInsightsId
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId
    serviceBusNamespaceId: serviceBus.outputs.serviceBusNamespaceId
    processingQueueName: serviceBus.outputs.extraccionQueueName
    opsEmailAddress: opsEmailAddress
  }
}

@description('Resource group id.')
output resourceGroupId string = rg.outputs.resourceGroupId

@description('Virtual network id.')
output virtualNetworkId string = network.outputs.virtualNetworkId

@description('Service Bus namespace id.')
output serviceBusNamespaceId string = serviceBus.outputs.serviceBusNamespaceId

@description('Service Bus namespace name.')
output serviceBusNamespaceName string = serviceBus.outputs.serviceBusNamespaceName

@description('Service Bus fully qualified namespace.')
output serviceBusFullyQualifiedNamespace string = serviceBus.outputs.serviceBusFullyQualifiedNamespace

@description('Flow 0 ingestion queue id.')
output ingestionQueueId string = serviceBus.outputs.ingestionQueueId

@description('Extraction queue id.')
output extraccionQueueId string = serviceBus.outputs.extraccionQueueId

@description('HITL decisions topic name.')
output hitlDecisionsTopicName string = serviceBus.outputs.hitlDecisionsTopicName

@description('Cosmos DB account id.')
output cosmosAccountId string = cosmos.outputs.cosmosAccountId

@description('Cosmos DB endpoint.')
output cosmosEndpoint string = cosmos.outputs.cosmosEndpoint

@description('Upload sessions container id.')
output uploadSessionsContainerId string = cosmos.outputs.uploadSessionsContainerId

@description('Storage account id.')
output storageAccountId string = storage.outputs.storageAccountId

@description('Storage account name.')
output storageAccountName string = storage.outputs.storageAccountName

@description('Storage account blob endpoint.')
output storageAccountUrl string = storageAccountUrl

@description('Key Vault id.')
output keyVaultId string = keyVault.outputs.keyVaultId

@description('Key Vault endpoint.')
output keyVaultUrl string = keyVault.outputs.keyVaultUri

@description('Log Analytics workspace id.')
output logAnalyticsWorkspaceId string = monitoring.outputs.logAnalyticsWorkspaceId

@description('Application Insights id.')
output applicationInsightsId string = monitoring.outputs.applicationInsightsId

@description('Application Insights connection string.')
output applicationInsightsConnectionString string = monitoring.outputs.applicationInsightsConnectionString

@description('Application Insights instrumentation key.')
output applicationInsightsInstrumentationKey string = monitoring.outputs.applicationInsightsInstrumentationKey

@description('Azure Communication Services resource id.')
output acsId string = acs.outputs.acsId

@description('Azure Communication Services endpoint.')
output acsEndpoint string = acs.outputs.acsEndpoint

@description('Azure-managed sender domain for HITL email.')
output emailSenderDomain string = acs.outputs.emailSenderDomain

@description('Azure AI Foundry account id.')
output aiServicesId string = aiFoundry.outputs.aiServicesId

@description('Azure AI Foundry account name.')
output aiServicesName string = aiFoundry.outputs.aiServicesName

@description('Azure AI Foundry endpoint.')
output aiServicesEndpoint string = aiFoundry.outputs.aiServicesEndpoint

@description('Azure AI Foundry project endpoint.')
output aiProjectEndpoint string = aiFoundry.outputs.aiProjectEndpoint

@description('Azure AI Foundry principal id.')
output aiServicesPrincipalId string = aiFoundry.outputs.aiServicesPrincipalId

@description('GPT-5 deployment name.')
output gpt5DeploymentName string = aiFoundry.outputs.gpt5DeploymentName

@description('GPT-5 mini deployment name.')
output gpt5MiniDeploymentName string = aiFoundry.outputs.gpt5MiniDeploymentName

@description('Document Intelligence account id.')
output docIntellId string = docIntell.outputs.docIntellId

@description('Document Intelligence endpoint.')
output docIntellEndpoint string = docIntell.outputs.docIntellEndpoint

@description('Azure Monitor action group id.')
output opsActionGroupId string = alerts.outputs.actionGroupId

@description('Container Apps environment id.')
output containerAppsEnvironmentId string = containerApps.outputs.managedEnvironmentId

@description('Container Apps environment default domain.')
output containerAppsEnvironmentDefaultDomain string = containerApps.outputs.managedEnvironmentDefaultDomain

@description('GitHub runner ACA environment name.')
output runnersEnvironmentName string = runners.outputs.runnerEnvironmentName

@description('GitHub runner ACA job name.')
output runnersJobName string = runners.outputs.runnerJobName

@description('Main orchestrator container app id.')
output orchestratorAppId string = containerApps.outputs.orchestratorAppId

@description('Flow 0 dedup ACA Job id.')
output flow0DedupJobId string = containerApps.outputs.flow0DedupJobId

@description('HITL web form container app id.')
output hitlWebformAppId string = containerApps.outputs.hitlWebformAppId

@description('Escalation timer ACA Job id.')
output escalationTimerJobId string = containerApps.outputs.escalationTimerJobId

@description('Upload-web container app id.')
output uploadWebAppId string = enableUploadWeb ? uploadWebApp.outputs.uploadWebAppId : ''

@description('Front Door endpoint hostname for upload-web.')
output frontDoorEndpointHostname string = enableUploadWeb ? frontDoor.outputs.frontDoorEndpointHostname : ''

@description('Front Door profile resource id.')
output frontDoorProfileId string = enableUploadWeb ? frontDoor.outputs.frontDoorProfileId : ''

@description('WAF policy resource id.')
output wafPolicyId string = enableUploadWeb ? frontDoor.outputs.wafPolicyId : ''

@description('Whether production-only network hardening is enabled.')
output networkHardeningEnabled bool = enableNetworkHardening

@description('Event Grid system topic id.')
output eventGridSystemTopicId string = eventGrid.outputs.systemTopicId

@description('Event Grid BlobCreated subscription id.')
output eventGridSubscriptionId string = eventGrid.outputs.eventSubscriptionId

@description('Identity assignment summary.')
output workloadIdentities object = identity.outputs.identities
