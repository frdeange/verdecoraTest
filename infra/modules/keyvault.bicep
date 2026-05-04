targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for Key Vault resources.')
param location string

@description('Key Vault name override. Defaults to the standard environment-specific name.')
param vaultName string = 'kv-albaranes-${environment}'

@description('Controls public network access during bootstrap and post-cutover hardening.')
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Disabled'

@description('Firewall default action for the Key Vault network ACLs.')
@allowed([
  'Allow'
  'Deny'
])
param networkDefaultAction string = 'Deny'

@description('Optional GitHub PAT value to seed into Key Vault during bootstrap.')
@secure()
param githubPat string = ''

@description('Key Vault secret name used for the GitHub runner PAT.')
param githubPatSecretName string = 'github-runner-pat'

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  'managed-by': 'bicep'
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: vaultName
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: {
      name: 'standard'
      family: 'A'
    }
    enablePurgeProtection: true
    enableRbacAuthorization: true
    publicNetworkAccess: publicNetworkAccess
    softDeleteRetentionInDays: 90
    networkAcls: {
      defaultAction: networkDefaultAction
      bypass: 'AzureServices'
    }
  }
}

resource githubPatSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(githubPat)) {
  parent: keyVault
  name: githubPatSecretName
  properties: {
    value: githubPat
  }
}

@description('Key Vault id.')
output keyVaultId string = keyVault.id

@description('Key Vault name.')
output keyVaultName string = keyVault.name

@description('Key Vault URI.')
output keyVaultUri string = keyVault.properties.vaultUri

@description('Versionless GitHub PAT secret URI.')
output githubPatSecretUri string = '${keyVault.properties.vaultUri}secrets/${githubPatSecretName}'
