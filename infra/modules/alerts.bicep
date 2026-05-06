targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for monitor resources.')
param location string

@description('Application Insights resource id used for custom-metric alerts.')
param applicationInsightsId string

@description('Log Analytics workspace resource id used for KQL alerts.')
param logAnalyticsWorkspaceId string

@description('Service Bus namespace resource id used for queue-depth alerts.')
param serviceBusNamespaceId string

@description('Service Bus queue name monitored for processing backlog.')
param processingQueueName string = 'extraccion-in'

@description('Notification email for the ops team action group.')
param opsEmailAddress string = 'ops@verdecora.example.com'

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  'managed-by': 'bicep'
}

var actionGroupName = 'ag-verdecora-ops-${environment}'
var actionGroupShortName = 'vdcops${take(environment, 6)}'

var bcMcpConnectionFailureQuery = '''
AppTraces
| where TimeGenerated >= ago(5m)
| extend props = column_ifexists("Properties", dynamic({}))
| extend message = tostring(Message)
| extend serverName = coalesce(tostring(props["mcp_server"]), tostring(props["dependency.target"]), '')
| where SeverityLevel >= 3
| where message has_any ('BC MCP', 'Business Central MCP', 'connection failed', 'connection lost')
    or serverName has 'bc-mcp'
| summarize FailureCount = count()
'''

var docIntelligenceTimeoutRateQuery = '''
let windowStart = ago(15m);
let docintRequests = AppDependencies
| where TimeGenerated >= windowStart
| extend props = column_ifexists("Properties", dynamic({}))
| where Name has 'Document Intelligence'
    or Target has 'cognitiveservices'
    or tostring(props["component"]) has 'document-intelligence';
let totalRequests = toscalar(docintRequests | count);
let timeoutRequests = toscalar(
    docintRequests
    | where ResultCode in ('408', '504')
        or Name has 'timeout'
        or tostring(props["error.type"]) has 'timeout'
        or tostring(props["failure_reason"]) has 'timeout'
        or (Success == false and tostring(props["exception.type"]) has 'Timeout')
    | count
);
print TimeoutRatePct = iff(totalRequests == 0, 0.0, todouble(timeoutRequests) * 100.0 / todouble(totalRequests))
'''

var agentProcessingP95Query = '''
AppDependencies
| where TimeGenerated >= ago(15m)
| extend props = column_ifexists("Properties", dynamic({}))
| extend customDimensions = column_ifexists("CustomDimensions", dynamic({}))
| extend agentName = coalesce(
    tostring(customDimensions["agent_name"]),
    tostring(customDimensions["agent_id"]),
    tostring(props["agent_name"]),
    tostring(props["agent_id"]),
    Name
)
| where agentName has_any ('A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'extractor', 'triage', 'coherence', 'validator', 'inventory', 'communication')
| summarize P95DurationSeconds = percentile(DurationMs, 95) / 1000.0
'''

resource opsActionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: actionGroupName
  location: 'global'
  tags: tags
  properties: {
    enabled: true
    groupShortName: actionGroupShortName
    emailReceivers: [
      {
        name: 'ops-email'
        emailAddress: opsEmailAddress
        useCommonAlertSchema: true
      }
    ]
  }
}

resource errorRateAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (environment == 'prod') {
  name: 'ma-verdecora-error-rate-${environment}'
  location: 'global'
  tags: tags
  properties: {
    description: 'Critical alert when the application emits a processing error-rate metric above 5% for 15 minutes.'
    severity: 0
    enabled: true
    scopes: [
      applicationInsightsId
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    targetResourceType: 'microsoft.insights/components'
    targetResourceRegion: location
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'processing-error-rate'
          criterionType: 'StaticThresholdCriterion'
          metricNamespace: 'microsoft.insights/components'
          metricName: 'processing_error_rate_pct'
          operator: 'GreaterThan'
          threshold: 5
          timeAggregation: 'Average'
          skipMetricValidation: true
        }
      ]
    }
    autoMitigate: true
    actions: [
      {
        actionGroupId: opsActionGroup.id
        webHookProperties: {
          alert_key: 'processing-error-rate'
          severity: 'critical'
        }
      }
    ]
  }
}

resource queueDepthAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'ma-verdecora-queue-depth-${environment}'
  location: 'global'
  tags: tags
  properties: {
    description: 'Warning alert when the extraccion-in queue depth remains above 100 messages.'
    severity: 2
    enabled: true
    scopes: [
      serviceBusNamespaceId
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    targetResourceType: 'Microsoft.ServiceBus/namespaces'
    targetResourceRegion: location
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'servicebus-queue-depth'
          criterionType: 'StaticThresholdCriterion'
          metricNamespace: 'Microsoft.ServiceBus/namespaces'
          metricName: 'ActiveMessages'
          operator: 'GreaterThan'
          threshold: 100
          timeAggregation: 'Average'
          dimensions: [
            {
              name: 'EntityName'
              operator: 'Include'
              values: [
                processingQueueName
              ]
            }
          ]
        }
      ]
    }
    autoMitigate: true
    actions: [
      {
        actionGroupId: opsActionGroup.id
        webHookProperties: {
          alert_key: 'servicebus-queue-depth'
          severity: 'warning'
          queue_name: processingQueueName
        }
      }
    ]
  }
}

resource hitlBacklogMetricAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (environment == 'prod') {
  name: 'ma-verdecora-hitl-backlog-${environment}'
  location: 'global'
  tags: tags
  properties: {
    description: 'Warning alert when the pending HITL backlog older than 24 hours exceeds 50 reviews.'
    severity: 2
    enabled: true
    scopes: [
      applicationInsightsId
    ]
    evaluationFrequency: 'PT15M'
    windowSize: 'PT30M'
    targetResourceType: 'microsoft.insights/components'
    targetResourceRegion: location
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'hitl-backlog-over-24h'
          criterionType: 'StaticThresholdCriterion'
          metricNamespace: 'microsoft.insights/components'
          metricName: 'hitl_pending_reviews_over_24h'
          operator: 'GreaterThan'
          threshold: 50
          timeAggregation: 'Average'
          skipMetricValidation: true
        }
      ]
    }
    autoMitigate: true
    actions: [
      {
        actionGroupId: opsActionGroup.id
        webHookProperties: {
          alert_key: 'hitl-backlog-over-24h'
          severity: 'warning'
        }
      }
    ]
  }
}

resource bcMcpConnectionFailuresAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: 'la-verdecora-bc-mcp-${environment}'
  location: location
  tags: tags
  kind: 'LogAlert'
  properties: {
    description: 'Detect repeated Business Central MCP connection failures.'
    displayName: 'Verdecora BC MCP connection failures'
    enabled: true
    severity: 1
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    scopes: [
      logAnalyticsWorkspaceId
    ]
    criteria: {
      allOf: [
        {
          query: bcMcpConnectionFailureQuery
          metricMeasureColumn: 'FailureCount'
          timeAggregation: 'Total'
          operator: 'GreaterThan'
          threshold: 3
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    autoMitigate: true
    actions: {
      actionGroups: [
        opsActionGroup.id
      ]
      customProperties: {
        alert_key: 'bc-mcp-connection-failures'
        severity: 'critical'
      }
    }
  }
}

resource docIntelligenceTimeoutAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: 'la-verdecora-docint-timeouts-${environment}'
  location: location
  tags: tags
  kind: 'LogAlert'
  properties: {
    description: 'Detect Document Intelligence timeout rates above 10% over the last 15 minutes.'
    displayName: 'Verdecora Document Intelligence timeout rate'
    enabled: true
    severity: 2
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    scopes: [
      logAnalyticsWorkspaceId
    ]
    criteria: {
      allOf: [
        {
          query: docIntelligenceTimeoutRateQuery
          metricMeasureColumn: 'TimeoutRatePct'
          timeAggregation: 'Maximum'
          operator: 'GreaterThan'
          threshold: 10
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    autoMitigate: true
    actions: {
      actionGroups: [
        opsActionGroup.id
      ]
      customProperties: {
        alert_key: 'document-intelligence-timeout-rate'
        severity: 'warning'
      }
    }
  }
}

resource agentProcessingTimeAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: 'la-verdecora-agent-p95-${environment}'
  location: location
  tags: tags
  kind: 'LogAlert'
  properties: {
    description: 'Detect p95 agent processing times above 60 seconds across A1-A6.'
    displayName: 'Verdecora agent processing p95'
    enabled: true
    severity: 1
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    scopes: [
      logAnalyticsWorkspaceId
    ]
    criteria: {
      allOf: [
        {
          query: agentProcessingP95Query
          metricMeasureColumn: 'P95DurationSeconds'
          timeAggregation: 'Maximum'
          operator: 'GreaterThan'
          threshold: 60
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    autoMitigate: true
    actions: {
      actionGroups: [
        opsActionGroup.id
      ]
      customProperties: {
        alert_key: 'agent-processing-p95'
        severity: 'critical'
      }
    }
  }
}

// ── Upload Web alerts (#118) ────────────────────────────────────────────

var uploadWeb5xxRateQuery = '''
let windowStart = ago(15m);
let totalRequests = toscalar(
    AppRequests
    | where TimeGenerated >= windowStart
    | where AppRoleName has 'upload-web'
    | count
);
let errorRequests = toscalar(
    AppRequests
    | where TimeGenerated >= windowStart
    | where AppRoleName has 'upload-web'
    | where toint(ResultCode) >= 500
    | count
);
print ErrorRatePct = iff(totalRequests == 0, 0.0, todouble(errorRequests) * 100.0 / todouble(totalRequests))
'''

var uploadWebAbandonedRateQuery = '''
let windowStart = ago(1h);
let created = toscalar(
    customMetrics
    | where TimeGenerated >= windowStart
    | where name == 'upload_sessions_created'
    | summarize sum(valueCount)
);
let abandoned = toscalar(
    customMetrics
    | where TimeGenerated >= windowStart
    | where name == 'upload_session_abandoned'
    | summarize sum(valueCount)
);
print AbandonedRatePct = iff(created == 0, 0.0, todouble(abandoned) * 100.0 / todouble(created))
'''

var uploadWebAuthFailureQuery = '''
AppRequests
| where TimeGenerated >= ago(5m)
| where AppRoleName has 'upload-web'
| where toint(ResultCode) in (401, 403)
| summarize AuthFailures = count()
'''

resource uploadWeb5xxAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: 'la-verdecora-upload-web-5xx-${environment}'
  location: location
  tags: tags
  kind: 'LogAlert'
  properties: {
    description: 'Critical: Upload Web 5xx error rate exceeds 5% over 15 minutes.'
    displayName: 'Upload Web 5xx error rate'
    enabled: true
    severity: 0
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    scopes: [
      logAnalyticsWorkspaceId
    ]
    criteria: {
      allOf: [
        {
          query: uploadWeb5xxRateQuery
          metricMeasureColumn: 'ErrorRatePct'
          timeAggregation: 'Maximum'
          operator: 'GreaterThan'
          threshold: 5
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    autoMitigate: true
    actions: {
      actionGroups: [
        opsActionGroup.id
      ]
      customProperties: {
        alert_key: 'upload-web-5xx-rate'
        severity: 'critical'
      }
    }
  }
}

resource uploadWebAbandonedAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: 'la-verdecora-upload-web-abandoned-${environment}'
  location: location
  tags: tags
  kind: 'LogAlert'
  properties: {
    description: 'Warning: Upload Web session abandonment rate exceeds 20% over 1 hour.'
    displayName: 'Upload Web session abandonment rate'
    enabled: true
    severity: 2
    evaluationFrequency: 'PT15M'
    windowSize: 'PT1H'
    scopes: [
      logAnalyticsWorkspaceId
    ]
    criteria: {
      allOf: [
        {
          query: uploadWebAbandonedRateQuery
          metricMeasureColumn: 'AbandonedRatePct'
          timeAggregation: 'Maximum'
          operator: 'GreaterThan'
          threshold: 20
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    autoMitigate: true
    actions: {
      actionGroups: [
        opsActionGroup.id
      ]
      customProperties: {
        alert_key: 'upload-web-abandoned-rate'
        severity: 'warning'
      }
    }
  }
}

resource uploadWebAuthFailureAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: 'la-verdecora-upload-web-auth-${environment}'
  location: location
  tags: tags
  kind: 'LogAlert'
  properties: {
    description: 'Warning: Upload Web auth failures exceed 10 in 5 minutes (possible brute force).'
    displayName: 'Upload Web auth failure spike'
    enabled: true
    severity: 2
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    scopes: [
      logAnalyticsWorkspaceId
    ]
    criteria: {
      allOf: [
        {
          query: uploadWebAuthFailureQuery
          metricMeasureColumn: 'AuthFailures'
          timeAggregation: 'Total'
          operator: 'GreaterThan'
          threshold: 10
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    autoMitigate: true
    actions: {
      actionGroups: [
        opsActionGroup.id
      ]
      customProperties: {
        alert_key: 'upload-web-auth-failures'
        severity: 'warning'
      }
    }
  }
}

@description('Action group resource id.')
output actionGroupId string = opsActionGroup.id
