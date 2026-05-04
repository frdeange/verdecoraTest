targetScope = 'resourceGroup'

@description('Name of the existing Key Vault. The vault must already be configured for Azure RBAC authorization.')
param keyVaultName string

@description('Resource ID of the Log Analytics workspace that receives Key Vault diagnostics.')
param logAnalyticsWorkspaceId string

@description('Optional tags applied to every placeholder secret.')
param placeholderTags object = {}

@description('Placeholder values written to Key Vault. Replace them immediately after deployment through a secure operational workflow.')
param placeholderValues object = {
  bcOAuthClientSecret: 'REPLACE-ME-BC-OAUTH-CLIENT-SECRET'
  acsConnectionString: 'REPLACE-ME-ACS-CONNECTION-STRING'
  githubRunnerPat: 'REPLACE-ME-GITHUB-RUNNER-PAT'
}

@description('Name of the diagnostic setting that forwards Key Vault audit logs to Log Analytics.')
param diagnosticSettingName string = 'send-to-log-analytics'

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource bcOAuthClientSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'bc-oauth-client-secret'
  properties: {
    value: placeholderValues.bcOAuthClientSecret
    contentType: 'BC MCP OAuth 2.0 Auth Code + PKCE client secret placeholder'
    attributes: {
      enabled: true
    }
  }
  tags: union(placeholderTags, {
    rotationPolicy: 'rotate-every-90-days'
    owner: 'security'
    usage: 'bc-mcp-confidential-client'
  })
}

resource acsConnectionString 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'acs-connection-string'
  properties: {
    value: placeholderValues.acsConnectionString
    contentType: 'Azure Communication Services email connection string placeholder'
    attributes: {
      enabled: true
    }
  }
  tags: union(placeholderTags, {
    rotationPolicy: 'rotate-every-30-days'
    owner: 'security'
    usage: 'acs-email-fallback-only'
  })
}

resource githubRunnerPat 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'github-runner-pat'
  properties: {
    value: placeholderValues.githubRunnerPat
    contentType: 'GitHub PAT placeholder for private runner bootstrap only'
    attributes: {
      enabled: true
    }
  }
  tags: union(placeholderTags, {
    rotationPolicy: 'rotate-every-30-days'
    owner: 'platform-security'
    usage: 'temporary-runner-bootstrap'
  })
}

resource keyVaultDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: keyVault
  name: diagnosticSettingName
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logAnalyticsDestinationType: 'Dedicated'
    logs: [
      {
        categoryGroup: 'audit'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
  }
}

output secretNames array = [
  bcOAuthClientSecret.name
  acsConnectionString.name
  githubRunnerPat.name
]
