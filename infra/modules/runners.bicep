targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for runner resources.')
param location string

@description('Subnet resource ID used by the internal ACA managed environment.')
param infrastructureSubnetId string

@description('Existing Key Vault name that stores the GitHub PAT secret.')
param keyVaultName string

@description('Key Vault secret URI for the GitHub PAT used by the KEDA scaler and runner bootstrap.')
param githubPatSecretUri string

@description('Repository URL that the runner pool will serve.')
param repoUrl string

@description('Prefix applied to GitHub runner names for easier discovery.')
param runnerNamePrefix string = 'verdecora'

@description('Container image used for the runner job. Override with a hardened custom image when available.')
param runnerImage string = 'ghcr.io/actions/actions-runner:latest'

@description('Container registry server for the runner image. When set, ACA authenticates with the runner managed identity.')
param runnerRegistryServer string = ''

@description('ACA managed environment name for runner jobs.')
param runnerEnvironmentName string = 'acae-runners-${environment}'

@description('ACA Job name for the GitHub runner pool.')
param runnerJobName string = 'job-gha-runner-${environment}'

@description('User-assigned managed identity name for the runner job.')
param runnerIdentityName string = 'id-gha-runner-${environment}'

@description('Log Analytics workspace name used by the runner environment.')
param logAnalyticsWorkspaceName string = 'log-runners-${environment}'

@description('Minimum number of job executions kept warm by the scaler.')
param minExecutions int = 0

@description('Maximum number of concurrent job executions created by the scaler.')
param maxExecutions int = 10

@description('Scale-rule polling interval in seconds.')
param pollingInterval int = 30

@description('Maximum execution time in seconds per runner job execution.')
param replicaTimeout int = 1800

@description('Retry attempts per job execution.')
param replicaRetryLimit int = 0

@description('CPU cores allocated to the runner container.')
param cpu int = 2

@description('Memory allocated to the runner container.')
param memory string = '4Gi'

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  workload: 'github-runners'
  'managed-by': 'bicep'
}

var normalizedRepoUrl = replace(replace(replace(repoUrl, 'https://github.com/', ''), 'http://github.com/', ''), '.git', '')
var repoSegments = split(normalizedRepoUrl, '/')
var repoOwner = repoSegments[0]
var repoName = repoSegments[1]
var githubApiUrl = 'https://api.github.com'
var registrationTokenApiUrl = '${githubApiUrl}/repos/${repoOwner}/${repoName}/actions/runners/registration-token'
var removeTokenApiUrl = '${githubApiUrl}/repos/${repoOwner}/${repoName}/actions/runners/remove-token'
var runnerStartupScript = 'set -euo pipefail; request_runner_token() { local url="$1"; curl -fsSL -X POST -H "Accept: application/vnd.github+json" -H "Authorization: Bearer $GITHUB_PAT" -H "X-GitHub-Api-Version: 2022-11-28" "$url" | sed -n "s/.*\\"token\\"[[:space:]]*:[[:space:]]*\\"\\([^\\"]*\\)\\".*/\\1/p"; }; RUNNER_DIR="$(dirname "$(find /home/runner /actions-runner -maxdepth 3 -name config.sh 2>/dev/null | head -n 1)")"; if [ -z "$RUNNER_DIR" ]; then echo "Unable to locate config.sh in the runner image."; exit 1; fi; RUNNER_NAME="$(printf "%s-%s-%s" "$RUNNER_NAME_PREFIX" "$(hostname)" "$(date +%s)")"; REGISTRATION_TOKEN="$(request_runner_token "$REGISTRATION_TOKEN_API_URL")"; if [ -z "$REGISTRATION_TOKEN" ]; then echo "Failed to acquire a GitHub registration token."; exit 1; fi; cleanup() { if [ -f "$RUNNER_DIR/.runner" ]; then REMOVE_TOKEN="$(request_runner_token "$REMOVE_TOKEN_API_URL" || true)"; if [ -n "$REMOVE_TOKEN" ]; then "$RUNNER_DIR/config.sh" remove --unattended --token "$REMOVE_TOKEN" || true; fi; fi; }; trap cleanup EXIT INT TERM; cd "$RUNNER_DIR"; echo "Configuring runner $RUNNER_NAME for $GH_URL"; ./config.sh --unattended --replace --ephemeral --url "$GH_URL" --token "$REGISTRATION_TOKEN" --name "$RUNNER_NAME" --work "_work"; echo "Runner $RUNNER_NAME registered; waiting for a job."; ./run.sh'
var keyVaultSecretsUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
var acrPushRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8311e382-0749-4cb8-b61a-304f252e45ec')
var contributorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')

@description('ACR resource id — required for AcrPush role assignment.')
param acrResourceId string = ''

@description('Resource group resource id — required for Contributor role on RG.')
param resourceGroupId string = ''

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  tags: tags
  properties: {
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
  sku: {
    name: 'PerGB2018'
  }
}

resource runnerIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: runnerIdentityName
  location: location
  tags: tags
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource keyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, runnerIdentity.name, keyVaultSecretsUserRoleDefinitionId)
  scope: keyVault
  properties: {
    principalId: runnerIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

// AcrPush — allows the runner to build and push images via `az acr build`
resource acrPushRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(acrResourceId)) {
  name: guid(acrResourceId, runnerIdentity.name, acrPushRoleDefinitionId, 'bicep')
  properties: {
    principalId: runnerIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPushRoleDefinitionId
  }
}

// Contributor on RG — allows the runner to update Container Apps via `az containerapp update`
resource rgContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(resourceGroupId)) {
  name: guid(resourceGroupId, runnerIdentity.name, contributorRoleDefinitionId, 'bicep')
  properties: {
    principalId: runnerIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: contributorRoleDefinitionId
  }
}

resource managedEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: runnerEnvironmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    vnetConfiguration: {
      infrastructureSubnetId: infrastructureSubnetId
      internal: true
    }
  }
}

resource runnerJob 'Microsoft.App/jobs@2025-01-01' = {
  name: runnerJobName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${runnerIdentity.id}': {}
    }
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      triggerType: 'Event'
      replicaTimeout: replicaTimeout
      replicaRetryLimit: replicaRetryLimit
      registries: empty(runnerRegistryServer)
        ? []
        : [
            {
              server: runnerRegistryServer
              identity: runnerIdentity.id
            }
          ]
      secrets: [
        {
          name: 'github-pat'
          identity: runnerIdentity.id
          keyVaultUrl: githubPatSecretUri
        }
      ]
      eventTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
        scale: {
          minExecutions: minExecutions
          maxExecutions: maxExecutions
          pollingInterval: pollingInterval
          rules: [
            {
              name: 'github-runner'
              type: 'github-runner'
              metadata: {
                githubAPIURL: githubApiUrl
                owner: repoOwner
                repos: repoName
                runnerScope: 'repo'
                targetWorkflowQueueLength: '1'
              }
              auth: [
                {
                  secretRef: 'github-pat'
                  triggerParameter: 'personalAccessToken'
                }
              ]
            }
          ]
        }
      }
    }
    template: {
      containers: [
        {
          name: 'github-runner'
          image: runnerImage
          command: [
            '/bin/bash'
          ]
          args: [
            '-lc'
            runnerStartupScript
          ]
          env: [
            {
              name: 'GITHUB_PAT'
              secretRef: 'github-pat'
            }
            {
              name: 'REPO_URL'
              value: repoUrl
            }
            {
              name: 'RUNNER_NAME_PREFIX'
              value: runnerNamePrefix
            }
            {
              name: 'GH_URL'
              value: 'https://github.com/${repoOwner}/${repoName}'
            }
            {
              name: 'REGISTRATION_TOKEN_API_URL'
              value: registrationTokenApiUrl
            }
            {
              name: 'REMOVE_TOKEN_API_URL'
              value: removeTokenApiUrl
            }
          ]
          resources: {
            cpu: cpu
            memory: memory
          }
        }
      ]
    }
  }
  dependsOn: [
    keyVaultSecretsUser
  ]
}

@description('Runner managed environment name.')
output runnerEnvironmentName string = managedEnvironment.name

@description('Runner job name.')
output runnerJobName string = runnerJob.name

@description('Runner managed identity resource ID.')
output runnerIdentityId string = runnerIdentity.id

@description('Runner managed identity principal ID.')
output runnerIdentityPrincipalId string = runnerIdentity.properties.principalId

@description('Log Analytics workspace resource ID for the runner environment.')
output logAnalyticsWorkspaceId string = logAnalytics.id
