targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for Container Apps resources.')
param location string

@description('Subnet resource ID delegated to the Container Apps environment.')
param infrastructureSubnetId string

@description('Name of the Log Analytics workspace used by the Container Apps environment.')
param logAnalyticsWorkspaceName string = 'log-albaranes-${environment}'

@description('Azure AI Foundry endpoint exposed to the orchestrator runtime.')
param aiServicesEndpoint string

@description('Cosmos DB endpoint exposed to the workloads.')
param cosmosEndpoint string

@description('Document Intelligence endpoint exposed to the orchestrator runtime.')
param docIntellEndpoint string

@description('Application Insights connection string injected into the workloads.')
param applicationInsightsConnectionString string

@description('Service Bus namespace name used by KEDA scale rules and runtime clients.')
param serviceBusNamespaceName string

@description('Queue name that receives raw BlobCreated events for Flow 0 dedup.')
param ingestionQueueName string = 'extraccion-queue'

@description('Queue name consumed by the main orchestrator app.')
param extractionQueueName string = 'extraccion-in'

@description('Topic name used by the HITL webform to publish review decisions.')
param hitlDecisionsTopicName string = 'hitl-decisions'

@description('Storage account blob endpoint exposed to the workloads.')
param storageAccountUrl string

@description('Azure Communication Services endpoint exposed to the workloads.')
param acsEndpoint string

@description('Key Vault endpoint exposed to the workloads.')
param keyVaultUrl string

@description('Microsoft Entra tenant id used for token validation.')
param tenantId string

@description('Azure Container Registry login server used for workload images.')
param acrLoginServer string

@description('Optional override for the orchestrator app image.')
param orchestratorImage string = ''

@description('Optional override for the Flow 0 dedup ACA Job image.')
param dedupJobImage string = ''

@description('Optional override for the HITL web form image.')
param hitlWebformImage string = ''

@description('Optional override for the escalation timer ACA Job image.')
param escalationTimerJobImage string = ''

@description('Optional override for the reconciliation ACA Job image.')
param reconciliationJobImage string = ''

@description('Optional override for the learning ACA Job image.')
param learningJobImage string = ''

@description('Deploy Post-MVP scheduled jobs (reconciliation + learning). Disable until real images are available.')
param enablePostMvpJobs bool = false

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  'managed-by': 'bicep'
}

var managedEnvironmentName = 'acae-verdecora-${environment}'
var serviceBusFullyQualifiedNamespace = '${serviceBusNamespaceName}.servicebus.windows.net'
var resolvedOrchestratorImage = empty(orchestratorImage) ? '${acrLoginServer}/verdecora-orchestrator:latest' : orchestratorImage
var resolvedDedupJobImage = empty(dedupJobImage) ? '${acrLoginServer}/verdecora-flow0-dedup:latest' : dedupJobImage
var resolvedHitlWebformImage = empty(hitlWebformImage) ? '${acrLoginServer}/verdecora-hitl-webform:latest' : hitlWebformImage
var resolvedEscalationTimerJobImage = empty(escalationTimerJobImage) ? '${acrLoginServer}/verdecora-escalation-timer:latest' : escalationTimerJobImage
var resolvedReconciliationJobImage = empty(reconciliationJobImage) ? 'mcr.microsoft.com/k8se/quickstart:latest' : reconciliationJobImage
var resolvedLearningJobImage = empty(learningJobImage) ? 'mcr.microsoft.com/k8se/quickstart:latest' : learningJobImage

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource managedEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: managedEnvironmentName
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

resource orchestratorApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'verdecora-orchestrator-${environment}'
  location: location
  tags: union(tags, {
    service: 'agentic-orchestrator'
  })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      dapr: {
        enabled: false
      }
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      ingress: {
        external: false
        targetPort: 8080
        transport: 'Auto'
      }
    }
    template: {
      containers: [
        {
          name: 'orchestrator'
          image: resolvedOrchestratorImage
          env: [
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: aiServicesEndpoint
            }
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosEndpoint
            }
            {
              name: 'DOCINTELL_ENDPOINT'
              value: docIntellEndpoint
            }
            {
              name: 'DOCUMENT_INTELLIGENCE_ENDPOINT'
              value: docIntellEndpoint
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
              value: serviceBusNamespaceName
            }
            {
              name: 'SERVICEBUS_FQ_NAMESPACE'
              value: serviceBusFullyQualifiedNamespace
            }
            {
              name: 'SERVICEBUS_QUEUE_NAME'
              value: extractionQueueName
            }
            {
              name: 'EXTRACTION_QUEUE_NAME'
              value: extractionQueueName
            }
            {
              name: 'STORAGE_ACCOUNT_URL'
              value: storageAccountUrl
            }
            {
              name: 'ACS_ENDPOINT'
              value: acsEndpoint
            }
            {
              name: 'KEY_VAULT_URL'
              value: keyVaultUrl
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: applicationInsightsConnectionString
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
        rules: [
          {
            name: 'orchestrator-servicebus'
            custom: {
              type: 'azure-servicebus'
              metadata: {
                queueName: extractionQueueName
                namespace: serviceBusNamespaceName
                messageCount: '1'
              }
              identity: 'system'
            }
          }
        ]
      }
    }
  }
}

resource flow0DedupJob 'Microsoft.App/jobs@2025-01-01' = {
  name: 'verdecora-dedup-job-${environment}'
  location: location
  tags: union(tags, {
    service: 'flow0-dedup'
  })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      triggerType: 'Event'
      replicaTimeout: 1800
      replicaRetryLimit: 1
      eventTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
        scale: {
          minExecutions: 0
          maxExecutions: 3
          pollingInterval: 30
          rules: [
            {
              name: 'flow0-dedup-servicebus'
              type: 'azure-servicebus'
              metadata: {
                queueName: ingestionQueueName
                namespace: serviceBusNamespaceName
                messageCount: '1'
              }
              identity: 'system'
            }
          ]
        }
      }
    }
    template: {
      containers: [
        {
          name: 'flow0-dedup'
          image: resolvedDedupJobImage
          env: [
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosEndpoint
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
              value: serviceBusNamespaceName
            }
            {
              name: 'SERVICEBUS_FQ_NAMESPACE'
              value: serviceBusFullyQualifiedNamespace
            }
            {
              name: 'FLOW0_SOURCE_QUEUE_NAME'
              value: ingestionQueueName
            }
            {
              name: 'FLOW0_TARGET_QUEUE_NAME'
              value: extractionQueueName
            }
            {
              name: 'STORAGE_ACCOUNT_URL'
              value: storageAccountUrl
            }
            {
              name: 'COSMOS_DATABASE_NAME'
              value: 'albaranes-db'
            }
            {
              name: 'COSMOS_CONTAINER_NAME'
              value: 'albaranes'
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
    }
  }
}

resource hitlWebformApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'verdecora-hitl-webform-${environment}'
  location: location
  tags: union(tags, {
    service: 'hitl-webform'
  })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      dapr: {
        enabled: false
      }
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 8000
        transport: 'Auto'
      }
    }
    template: {
      containers: [
        {
          name: 'hitl-webform'
          image: resolvedHitlWebformImage
          env: [
            {
              name: 'SERVICE_BUS_NAMESPACE'
              value: serviceBusNamespaceName
            }
            {
              name: 'SERVICEBUS_FQ_NAMESPACE'
              value: serviceBusFullyQualifiedNamespace
            }
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosEndpoint
            }
            {
              name: 'STORAGE_ACCOUNT_URL'
              value: storageAccountUrl
            }
            {
              name: 'ACS_ENDPOINT'
              value: acsEndpoint
            }
            {
              name: 'HITL_DECISIONS_TOPIC_NAME'
              value: hitlDecisionsTopicName
            }
            {
              name: 'KEY_VAULT_URL'
              value: keyVaultUrl
            }
            {
              name: 'AZURE_TENANT_ID'
              value: tenantId
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

resource escalationTimerJob 'Microsoft.App/jobs@2025-01-01' = {
  name: 'verdecora-escalation-timer-${environment}'
  location: location
  tags: union(tags, {
    service: 'escalation-timer'
  })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      triggerType: 'Schedule'
      replicaTimeout: 1800
      replicaRetryLimit: 1
      scheduleTriggerConfig: {
        cronExpression: '0 * * * *'
        parallelism: 1
        replicaCompletionCount: 1
      }
    }
    template: {
      containers: [
        {
          name: 'escalation-timer'
          image: resolvedEscalationTimerJobImage
          env: [
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosEndpoint
            }
            {
              name: 'ACS_ENDPOINT'
              value: acsEndpoint
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
              value: serviceBusNamespaceName
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
    }
  }
}

resource reconciliationJob 'Microsoft.App/jobs@2025-01-01' = if (enablePostMvpJobs) {
  name: 'verdecora-reconciliation-${environment}'
  location: location
  tags: union(tags, {
    service: 'reconciliation'
  })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      triggerType: 'Schedule'
      replicaTimeout: 1800
      replicaRetryLimit: 1
      scheduleTriggerConfig: {
        cronExpression: '0 6 * * *'
        parallelism: 1
        replicaCompletionCount: 1
      }
    }
    template: {
      containers: [
        {
          name: 'reconciliation'
          image: resolvedReconciliationJobImage
          env: [
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosEndpoint
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
              value: serviceBusNamespaceName
            }
            {
              name: 'ACS_ENDPOINT'
              value: acsEndpoint
            }
            {
              name: 'AZURE_AI_PROJECT_ENDPOINT'
              value: aiServicesEndpoint
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
    }
  }
}

resource learningJob 'Microsoft.App/jobs@2025-01-01' = if (enablePostMvpJobs) {
  name: 'verdecora-learning-${environment}'
  location: location
  tags: union(tags, {
    service: 'learning'
  })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      triggerType: 'Schedule'
      replicaTimeout: 1800
      replicaRetryLimit: 1
      scheduleTriggerConfig: {
        cronExpression: '0 4 * * 0'
        parallelism: 1
        replicaCompletionCount: 1
      }
    }
    template: {
      containers: [
        {
          name: 'learning'
          image: resolvedLearningJobImage
          env: [
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosEndpoint
            }
            {
              name: 'AZURE_AI_PROJECT_ENDPOINT'
              value: aiServicesEndpoint
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
    }
  }
}

@description('Container Apps managed environment id.')
output managedEnvironmentId string = managedEnvironment.id

@description('Container Apps managed environment name.')
output managedEnvironmentName string = managedEnvironment.name

@description('Container Apps managed environment default domain.')
output managedEnvironmentDefaultDomain string = managedEnvironment.properties.defaultDomain

@description('Main orchestrator container app id.')
output orchestratorAppId string = orchestratorApp.id

@description('Main orchestrator managed identity principal id.')
output orchestratorPrincipalId string = orchestratorApp.identity.principalId

@description('Flow 0 dedup ACA Job id.')
output flow0DedupJobId string = flow0DedupJob.id

@description('Flow 0 dedup ACA Job managed identity principal id.')
output flow0DedupPrincipalId string = flow0DedupJob.identity.principalId

@description('HITL web form container app id.')
output hitlWebformAppId string = hitlWebformApp.id

@description('HITL web form managed identity principal id.')
output hitlWebformPrincipalId string = hitlWebformApp.identity.principalId

@description('Escalation timer ACA Job id.')
output escalationTimerJobId string = escalationTimerJob.id

@description('Escalation timer ACA Job managed identity principal id.')
output escalationTimerPrincipalId string = escalationTimerJob.identity.principalId

@description('Reconciliation ACA Job id.')
output reconciliationJobId string = enablePostMvpJobs ? reconciliationJob.id : ''

@description('Reconciliation ACA Job managed identity principal id.')
output reconciliationPrincipalId string = enablePostMvpJobs ? reconciliationJob.identity.principalId : ''

@description('Learning ACA Job id.')
output learningJobId string = enablePostMvpJobs ? learningJob.id : ''

@description('Learning ACA Job managed identity principal id.')
output learningPrincipalId string = enablePostMvpJobs ? learningJob.identity.principalId : ''
