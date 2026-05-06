targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for Event Grid resources.')
param location string

@description('Name of the storage account that emits BlobCreated events.')
param storageAccountName string

@description('Name of the Service Bus namespace that receives Event Grid deliveries.')
param serviceBusNamespaceName string

@description('Name of the ingestion queue that buffers BlobCreated events for Flow 0.')
param queueName string = 'extraccion-queue'

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  'managed-by': 'bicep'
}

var serviceBusDataSenderRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' existing = {
  name: serviceBusNamespaceName
}

resource ingestionQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' existing = {
  parent: serviceBusNamespace
  name: queueName
}

resource systemTopic 'Microsoft.EventGrid/systemTopics@2025-02-15' = {
  name: 'eg-st-albaranes-${environment}'
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    source: storageAccount.id
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
}

resource eventGridQueueSenderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(ingestionQueue.id, systemTopic.name, serviceBusDataSenderRoleDefinitionId)
  scope: ingestionQueue
  properties: {
    principalId: systemTopic.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: serviceBusDataSenderRoleDefinitionId
  }
}

resource blobCreatedSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2025-02-15' = {
  parent: systemTopic
  name: 'blobcreated-to-extraccion-queue'
  properties: {
    destination: any({
      endpointType: 'ServiceBusQueue'
      properties: {
        resourceId: ingestionQueue.id
        deliveryWithResourceIdentity: {
          identity: {
            type: 'SystemAssigned'
          }
        }
      }
    })
    eventDeliverySchema: 'EventGridSchema'
    filter: {
      includedEventTypes: [
        'Microsoft.Storage.BlobCreated'
      ]
      // upload-web writes blobs under albaranes-raw/{session_id}/... (and deeper nested prefixes),
      // so filtering at the container blob root keeps Event Grid -> Flow 0 working for every new upload path.
      subjectBeginsWith: '/blobServices/default/containers/albaranes-raw/blobs/'
      isSubjectCaseSensitive: false
    }
    retryPolicy: {
      maxDeliveryAttempts: 30
      eventTimeToLiveInMinutes: 1440
    }
  }
  dependsOn: [
    eventGridQueueSenderRoleAssignment
  ]
}

@description('Event Grid system topic id.')
output systemTopicId string = systemTopic.id

@description('Event Grid event subscription id.')
output eventSubscriptionId string = blobCreatedSubscription.id
