# Dallas — Bicep foundation (Sprint 0)

## Decision summary
- Implemented base Bicep modules for core infrastructure in `infra/modules` with a subscription-scope `main.bicep` orchestrator.
- Standardized tags across all resources (`project=verdecora-albaranes`, `env`, `managed-by=bicep`) and set `publicNetworkAccess` to `Disabled` where supported to align with private endpoint readiness.
- Storage account naming uses a hyphenless variant of `st-albaranes-{env}` to satisfy Azure naming constraints while preserving the naming convention intent.

## Notes
- Service Bus topic `albaran-events` includes subscriptions `albaran-recibido` and `albaran-validado`.
- Storage immutability policy on `albaranes-raw` uses an unlocked 30-day retention as a baseline.
