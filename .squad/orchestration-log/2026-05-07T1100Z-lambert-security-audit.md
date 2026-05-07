# Lambert — Security Audit
**Date:** 2026-05-07T11:00Z
**Status:** Completed
**Scope:** Azure exposure posture of `rg-verdecoratest-dev` (GPS Demo Subscription)

## Summary
Audited and locked down 8 Azure resources before E2E. Public surface reduced to Front Door + Upload Web Container App FQDN. AI Services, Document Intelligence, Cosmos DB, and ACR now have `publicNetworkAccess=Disabled`. Key Vault, Storage, Service Bus already compliant.

## Changes Made
- `verdecora-ais-dev`: `publicNetworkAccess=Disabled` + `networkAcls.defaultAction=Deny`
- `verdecora-docintell-dev`: `publicNetworkAccess=Disabled`
- `cosmos-albaranes-dev`: `publicNetworkAccess=Disabled` + removed temp firewall rule
- `acralbaranesdev`: `publicNetworkAccess=Disabled`
- `afd-verdecora-dev`: Left public (intentional)
- `verdecora-upload-web-dev`: Left unchanged (external ingress by design)

## Decisions Recorded
- Audit results and recommendations in `.squad/decisions.md` § "2026-05-07: Lambert — Security audit"
- Inbox file `lambert-security-audit.md` merged and deleted
