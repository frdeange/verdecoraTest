# Backend Services

- Webhook handlers for system events
- Change feed processors
- Integration services
- `flow0_dedup/` — ACA Job that deduplicates BlobCreated events and forwards normalized work items to the extraction queue

All services use async/await patterns with Python 3.12+.
