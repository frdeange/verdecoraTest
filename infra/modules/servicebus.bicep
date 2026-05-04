targetScope = 'resourceGroup'

@description('Deployment environment name (dev/test/prod).')
param environment string

@description('Azure region for Service Bus resources.')
param location string

var tags = {
  project: 'verdecora-albaranes'
  env: environment
  'managed-by': 'bicep'
}

var namespaceName = 'sb-albaranes-${environment}'

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: namespaceName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    disableLocalAuth: true
    publicNetworkAccess: 'Disabled'
  }
}

resource extraccionQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  name: '${serviceBusNamespace.name}/extraccion-in'
  properties: {
    enablePartitioning: true
  }
}

resource albaranEventsTopic 'Microsoft.ServiceBus/namespaces/topics@2022-10-01-preview' = {
  name: '${serviceBusNamespace.name}/albaran-events'
  properties: {
    enablePartitioning: true
  }
}

resource albaranRecibidoSubscription 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2022-10-01-preview' = {
  name: '${serviceBusNamespace.name}/albaran-events/albaran-recibido'
  properties: {
    maxDeliveryCount: 10
  }
}

resource albaranValidadoSubscription 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2022-10-01-preview' = {
  name: '${serviceBusNamespace.name}/albaran-events/albaran-validado'
  properties: {
    maxDeliveryCount: 10
  }
}

@description('Service Bus namespace id.')
output serviceBusNamespaceId string = serviceBusNamespace.id

@description('Queue id.')
output extraccionQueueId string = extraccionQueue.id

@description('Topic id.')
output albaranEventsTopicId string = albaranEventsTopic.id

@description('Subscription (recibido) id.')
output albaranRecibidoSubscriptionId string = albaranRecibidoSubscription.id

@description('Subscription (validado) id.')
output albaranValidadoSubscriptionId string = albaranValidadoSubscription.id
