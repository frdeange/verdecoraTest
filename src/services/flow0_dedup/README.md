# Flow 0 dedup ACA Job

This package implements the Sprint 2 Flow 0 adapter that runs inside an Azure Container Apps Job.

## Responsibilities

1. Receive a `BlobCreated` Event Grid notification from the Service Bus ingestion queue.
2. Deduplicate the blob using `blob_hash`, `etag`, or a `blob_name + event_date` fallback.
3. Seed a Cosmos DB processing record with `status = pending`.
4. Forward a normalized message to the extraction queue for the MAF orchestrator pipeline.

## Runtime configuration

- `COSMOS_ENDPOINT`
- `SERVICE_BUS_NAMESPACE` or `SERVICEBUS_FQ_NAMESPACE`
- `FLOW0_SOURCE_QUEUE_NAME` (default: `extraccion-queue`)
- `FLOW0_TARGET_QUEUE_NAME` (default: `extraccion-in`)
- `COSMOS_DATABASE_NAME` (default: `albaranes-db`)
- `COSMOS_CONTAINER_NAME` (default: `albaranes`)

All Azure clients use `DefaultAzureCredential`, so the ACA Job must run with a managed identity that has Cosmos DB and Service Bus RBAC.
