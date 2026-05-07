# Bootstrap guide — private VNet + self-hosted runners

This guide covers **Phase 0** for issue #4: create the Sweden Central private control plane, stand up the self-hosted GitHub Actions runner pool in Azure Container Apps (ACA), and hand all later deployments to that runner pool.

## Target bootstrap scope

- **Region:** Sweden Central
- **Subscription:** `0acbc8a1-0f3e-498e-b86b-6fa5468730e2`
- **Resource group:** `rg-verdecoratest-dev`
- **Repository:** `https://github.com/frdeange/verdecoraTest`

After this bootstrap succeeds, **all subsequent IaC deployments should go through the self-hosted runner** instead of a developer workstation or GitHub-hosted runner.

## What gets deployed

`infra/bootstrap/bootstrap.bicep` creates the minimal private deployment control plane:

1. resource group
2. VNet + subnets (via Dallas's `infra/modules/network.bicep`)
3. Key Vault for the bootstrap GitHub PAT
4. internal ACA managed environment in `snet-runners`
5. ACA Job with the `github-runner` KEDA scale rule
6. user-assigned managed identity for the runner job

## Prerequisites

- Azure CLI installed and authenticated to the target subscription.
- Azure CLI account can create resource groups, ACA environments, ACA jobs, managed identities, and Key Vault resources.
- PowerShell 7+ (recommended).
- A GitHub fine-grained PAT with at least:
  - `repo`
  - `actions`
- Repository admin/maintainer permission to register self-hosted runners.
- Awareness that ACA runners are intended for **private IaC/control-plane jobs**, not Docker-in-Docker workloads.

## Bootstrap steps

1. Open PowerShell in the repository root.
2. Sign in to Azure if needed:
   ```powershell
   az login
   az account set --subscription 0acbc8a1-0f3e-498e-b86b-6fa5468730e2
   ```
3. Run the bootstrap script and provide the PAT interactively:
   ```powershell
   .\infra\bootstrap\bootstrap.ps1 `
     -GitHubPat (Read-Host 'GitHub PAT' -AsSecureString)
   ```
4. The script will:
   - create `rg-verdecoratest-dev`
   - deploy `bootstrap.bicep`
   - validate the ACA environment + ACA job
   - start a manual ACA job execution
   - poll the GitHub Actions runners API until a runner whose name starts with `verdecora` appears

## How to verify the runner is registered

### Azure-side checks

```powershell
az containerapp env show --name acae-runners-dev --resource-group rg-verdecoratest-dev
az containerapp job show --name job-gha-runner-dev --resource-group rg-verdecoratest-dev
az containerapp job execution list --name job-gha-runner-dev --resource-group rg-verdecoratest-dev --output table
```

### GitHub-side checks

- UI path: **Repository → Settings → Actions → Runners**
- CLI/API check:
  ```powershell
  gh api repos/frdeange/verdecoraTest/actions/runners
  ```

A successful bootstrap should show at least one runner whose name starts with the configured `RUNNER_NAME_PREFIX`.

## Temporary bootstrap concessions

Phase 0 intentionally keeps the Key Vault reachable so the runner job can resolve the PAT secret before private endpoints are in place. This is a controlled bootstrap exception, not the end state.

## How to lock down the network after bootstrap

1. Add private endpoints + private DNS for Key Vault, Storage, Cosmos DB, Service Bus, and other private data-plane services.
2. Validate name resolution and data-plane access **from inside the VNet** using the ACA self-hosted runner.
3. Remove temporary public access from Key Vault and any other services left open for bootstrap.
4. Route runner egress through the chosen controlled path (NAT Gateway or, preferably, Azure Firewall for outbound logging).
5. Rotate the GitHub PAT after the first successful runner bootstrap and store the replacement secret in Key Vault.
6. Update GitHub workflows so private IaC/deployment jobs target the self-hosted runner labels only.

## Operational notes

- The ACA runner pattern is viable for Bicep, ARM, `az`, `azd`, Python tests, and private validation work.
- The runner image must include Azure CLI because `azure/login@v2` and the deploy scripts shell out to `az`; the post-bootstrap/main deployment now swaps the public bootstrap image for the private `github-runner-azure-cli` image in ACR.
- Do **not** rely on ACA runners for Docker-heavy builds, Docker Compose, service containers, or `kind`.
- If the team needs container image builds later, prefer `az acr build` / ACR Tasks or a separate VM-based runner pool.
