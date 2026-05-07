# Parker — Orchestrator E2E decisions

## 2026-05-07
- Updated orchestrator OCR flow to analyze downloaded blob bytes via Document Intelligence base64 input instead of passing the raw blob URL. This avoids failures when the storage account is private and Doc Intelligence cannot fetch the blob directly.
- Extended orchestrator queue deserialization to accept raw Event Grid BlobCreated payloads in addition to Flow 0 forwarded messages, mapping Event Grid metadata into an `OrchestrationRequest` with a stable `processing_id` from the event id.
- Normalized agent construction for Reconciliation/Learning to match the current Agent Framework `Agent(...)` signature and set GPT-5-safe default options (`max_tokens` translated by the SDK to `max_completion_tokens`).
- Added a live integration test gated by `RUN_LIVE_AZURE_TESTS=1`; on this runner the Service Bus data plane is IP-filtered, so the live test now skips with an explicit infrastructure reason instead of failing indistinctly.
