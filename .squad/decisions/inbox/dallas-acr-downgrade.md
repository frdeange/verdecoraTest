# 2026-05-07 — Dallas — ACR downgrade follow-up for issue #171

- Requested by Kiko de Angel to complete the ACR rollback from Premium/private to Standard/public for `acralbaranesdev` in `rg-verdecoratest-dev`.
- IaC changes remove the ACR agent pool model and the ACR private endpoint / `privatelink.azurecr.io` DNS assets while keeping other private endpoints intact.
- Workflow changes remove `ACR_AGENT_POOL` and all `--agent-pool` flags so `az acr build` uses the registry's default Standard capability set.
- Runtime sequence executed in Azure: delete agent pool, delete ACR private endpoint, delete ACR private DNS VNet link, delete ACR private DNS zone, downgrade ACR SKU to Standard.
- Verification target: ACR remains reachable for Container Apps through managed identity-based `AcrPull`, while the registry is now public (`publicNetworkAccess=Enabled`) and no ACR PE/DNS artifacts remain.
