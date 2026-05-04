targetScope = 'subscription'

@description('Deployment environment name.')
param environment string = 'dev'

@description('Azure region for bootstrap resources.')
param location string = 'swedencentral'

@description('Target resource group for the private platform bootstrap.')
param resourceGroupName string = 'rg-verdecoratest-dev'

@description('Repository URL that the self-hosted runner pool serves.')
param repoUrl string = 'https://github.com/frdeange/verdecoraTest'

@description('Prefix applied to ephemeral runner names.')
param runnerNamePrefix string = 'verdecora'

@description('Runner image used by the ACA Job. Override with a hardened custom image when available.')
param runnerImage string = 'ghcr.io/actions/actions-runner:latest'

@description('Bootstrap PAT stored in Key Vault and used by the runner scaler/registration flow.')
@secure()
param githubPat string

var deploymentSuffix = uniqueString(resourceGroupName, repoUrl)

module resourceGroupModule '../modules/resource-group.bicep' = {
  name: 'bootstrap-resource-group'
  params: {
    environment: environment
    location: location
    resourceGroupName: resourceGroupName
  }
}

module network '../modules/network.bicep' = {
  name: 'bootstrap-network'
  scope: resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
  }
  dependsOn: [
    resourceGroupModule
  ]
}

module keyVault '../modules/keyvault.bicep' = {
  name: 'bootstrap-keyvault'
  scope: resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
    publicNetworkAccess: 'Enabled'
    networkDefaultAction: 'Allow'
    githubPat: githubPat
    githubPatSecretName: 'github-runner-pat'
  }
  dependsOn: [
    resourceGroupModule
  ]
}

module runners '../modules/runners.bicep' = {
  name: 'bootstrap-runners-${deploymentSuffix}'
  scope: resourceGroup(resourceGroupName)
  params: {
    environment: environment
    location: location
    infrastructureSubnetId: network.outputs.subnetRunnersId
    keyVaultName: keyVault.outputs.keyVaultName
    githubPatSecretUri: keyVault.outputs.githubPatSecretUri
    repoUrl: repoUrl
    runnerNamePrefix: runnerNamePrefix
    runnerImage: runnerImage
  }
}

@description('Bootstrap resource group name.')
output resourceGroupName string = resourceGroupName

@description('Key Vault name that stores the bootstrap PAT.')
output keyVaultName string = keyVault.outputs.keyVaultName

@description('Versionless Key Vault secret URI used by the runner job.')
output githubPatSecretUri string = keyVault.outputs.githubPatSecretUri

@description('Runner ACA managed environment name.')
output runnerEnvironmentName string = runners.outputs.runnerEnvironmentName

@description('Runner ACA job name.')
output runnerJobName string = runners.outputs.runnerJobName

@description('Reminder for post-bootstrap operations.')
output nextStep string = 'Bootstrap complete. Route all later deployments through the self-hosted ACA runner pool and remove temporary public access once private endpoints are validated.'
