# Brett — Private Networking & Self-Hosted Runner Analysis

> **Author:** Brett (Private Network & CI/CD Specialist)
> **Requested by:** Kiko de Angel
> **Date:** 2026-05-03
> **Scope:** Azure private networking, Private Endpoints, and self-hosted GitHub Actions runners on Azure Container Apps (ACA) in **Sweden Central**.

---

## 1. Executive Summary

**Verdict:** The pattern is **viable** if we define it correctly as **private inbound + controlled public egress**.

1. **Self-hosted GitHub Actions runners on ACA are a real pattern in 2026**, and Microsoft documents them as **event-driven ACA Jobs** using the `github-runner` scale rule (KEDA-backed). For this use case, **ACA Jobs are the right primitive**, not always-on ACA Apps.
2. **The bootstrap sequence Kiko proposed is sound**:
   - **Phase 0:** deploy VNet + ACA runner environment + runner job while target services still allow public access.
   - **Phase 1:** create Private Endpoints + Private DNS, validate private name resolution, then disable public network access.
   - **Phase 2:** all later IaC deployments run from the ACA self-hosted runners.
3. **The biggest caveat is not networking — it is runner capability.** ACA Jobs **cannot run Docker-in-Docker**, so workflows that rely on `docker build`, service containers, Docker Compose, or `kind` will fail on ACA runners. These runners are excellent for **Bicep/Terraform/az/azd/Python tests**, but **not** as a universal build worker.
4. **GitHub itself is still a public SaaS dependency.** The runner can sit inside a private VNet, but it still needs controlled outbound access to GitHub APIs, token endpoints, package feeds, and Microsoft control-plane endpoints.

**Recommended platform stance:**
- Use **two ACA workload-profile environments** in one Sweden Central VNet:
  - one **internal app environment** for the product workloads,
  - one **runner environment** for CI/CD jobs.
- Put **all Private Endpoints in a dedicated subnet**.
- Put **NAT Gateway or Azure Firewall egress** on the ACA subnets so outbound is deterministic.
- Treat ACA runners as the **private IaC/control-plane runner pool**, not the image-building pool.

---

## 2. Self-Hosted GitHub Runners in ACA — 2026 Status

## 2.1 How the pattern works

Microsoft's current tutorial for GitHub Actions on ACA uses:
- an **Azure Container Apps Job**,
- configured as an **event-driven job**,
- with the **`github-runner` scale rule**,
- so new job executions start when GitHub has queued workflow work.

This is the right fit because a GitHub runner is naturally **ephemeral**:
- runner starts,
- registers with GitHub,
- executes one workflow job,
- exits.

That gives us **scale-to-zero** and avoids paying for idle VMs.

## 2.2 ACA Job vs ACA App

| Option | Fit for GitHub runners | Why |
|---|---:|---|
| **ACA Job** | **Yes** | Best match for short-lived, event-driven, one-job-per-runner behavior. |
| ACA App | Limited | Better for long-running services, not ephemeral CI workers. |

## 2.3 Scaling model

Scaling is based on the **GitHub Actions queue**, not HTTP traffic.
The job uses the `github-runner` scale rule (KEDA-backed) to poll GitHub and start runner executions.

Operationally, this means:
- no permanently idle runner nodes,
- burst scaling is possible,
- each execution should be treated as disposable.

## 2.4 Container image choice

Use a **custom runner image**.

Practical options:
1. **Preferred:** build your own image from the GitHub Actions runner binary (the Microsoft tutorial uses the Azure sample `Dockerfile.github`).
2. Acceptable: fork the sample and add only the tools you need (`az`, `bicep`, `gh`, Terraform, Python, PowerShell, etc.).
3. Avoid depending blindly on third-party community images for production CI.

**Recommendation for this project:**
Create a **minimal internal runner image** with:
- GitHub runner binary,
- Azure CLI,
- Bicep,
- `gh`,
- Python toolchain,
- any IaC linters used by the repo.

Do **not** treat the runner image as a generic build box.

## 2.5 GitHub authentication model

There are really **two** auth paths:

### A. Auth used by the scaler / runner bootstrap to GitHub
Microsoft's ACA tutorial uses a **GitHub fine-grained PAT** stored as an ACA secret. That PAT is used to:
- let the scale rule watch the workflow queue,
- let the container request a **short-lived registration token** from GitHub,
- register the runner at startup.

The runner itself should then register using the **ephemeral registration token**, not a long-lived registration secret.

### B. Auth used by workflows to Azure
For Azure deployments, prefer **GitHub OIDC federation** (`azure/login` with federated credentials), not a long-lived client secret.

### Practical recommendation
- **Short term / simplest:** fine-grained PAT in Key Vault, injected into the ACA Job as a secret.
- **More robust / enterprise-preferred:** move to **GitHub App** authentication if/where the scaler implementation supports it in the underlying KEDA path.
- In all cases, use **ephemeral runner registration tokens** at container startup.

## 2.6 Critical limitation: no Docker workloads inside ACA runners

Microsoft explicitly notes that **Container Apps and jobs do not support running Docker inside the container**.

That means ACA runners are **not suitable** for workflows that depend on:
- `docker build` / `docker buildx`,
- service containers,
- Docker Compose,
- `kind`,
- privileged container build steps.

### Impact on our project
ACA runners are **excellent** for:
- Bicep/Terraform deployment,
- `az` / `azd` / ARM management-plane operations,
- Python/unit/integration tests that do not require Docker,
- policy checks, linting, documentation pipelines.

ACA runners are **poor** for:
- building container images locally inside the runner.

### Mitigation
Split CI into two pools if needed:
- **ACA private runners** for private-network IaC and deployment.
- **Remote image build path** for containers, e.g. `az acr build` / ACR Tasks, or a separate VM-based self-hosted runner pool if Docker-heavy workflows are unavoidable.

---

## 3. Bootstrap Strategy (Chicken-and-Egg)

## 3.1 Recommended phased rollout

### Phase 0 — Public bootstrap of the private control plane
Deploy from a developer machine or a temporary GitHub-hosted runner:
- VNet
- subnets
- Private DNS zones
- runner ACA environment
- runner ACA Job
- optional ACR / Key Vault / Log Analytics

At this phase, target services may still have **public network access temporarily enabled**.

### Phase 1 — Private-link cutover
Deploy and validate:
- Private Endpoints,
- DNS zone links,
- name resolution from inside the VNet,
- ACA runner reachability to private FQDNs,
- then disable public network access on each service.

**Important ordering rule:**
Create **Private Endpoint + DNS + validation first**, then disable public access.

### Phase 2 — Private steady state
After the runner is proven:
- all later IaC runs execute from **self-hosted ACA runners**,
- all target PaaS services stay **private-only**,
- GitHub-hosted runners no longer deploy into the private estate.

## 3.2 Is the pattern viable?

**Yes — with guardrails.**

The pattern is viable because ARM/Bicep/Terraform deployments are **management-plane** operations; they do **not** require the runner itself to be inside the private network until you start doing:
- private DNS validation,
- data-plane configuration,
- private-only smoke tests,
- secret retrieval against private-only Key Vault endpoints,
- storage/cosmos/service-bus data-plane actions.

That is exactly why the runner should be bootstrapped **before** the final lock-down.

## 3.3 Practical gotchas

1. **GitHub remains public.** This is not an "air-gapped" pattern.
2. **Post-lockdown validations must run from inside the VNet.** A public runner can still deploy ARM resources, but it cannot validate private-only endpoints.
3. **If the bootstrap workflow writes secrets/data via data-plane APIs after public access is disabled, it will fail unless already running privately.**
4. **PAT rotation must be planned** if PAT auth is used for the scaler.
5. **ACR/private registry ordering matters.** Don't make the runner image source private-only before the ACA environment can resolve and pull from it.

---

## 4. Recommended Sweden Central VNet Topology

## 4.1 Proposed topology

**Recommended VNet:** `vnet-verdecora-core-swe` in **Sweden Central**

Suggested address space:
- `10.60.0.0/16`

Suggested subnets:

| Subnet | Suggested CIDR | Purpose | Notes |
|---|---:|---|---|
| `snet-aca-apps` | `/23` | Internal ACA environment for application workloads | ACA workload-profile environment; dedicated subnet required. `/27` is the technical minimum, but `/23` is safer for growth and reserved IP consumption. |
| `snet-aca-runners` | `/23` | ACA environment dedicated to self-hosted GitHub runner jobs | Separate environment isolates CI/CD blast radius from app workloads. |
| `snet-private-endpoints` | `/24` | All Private Endpoints | Keep PE NICs centralized for DNS and policy clarity. |
| `snet-foundry-agents` *(optional)* | `/24` | Foundry Agent Service delegated subnet if hosted/private agents are used | Foundry docs recommend `/24`; dedicated per Foundry resource. |

## 4.2 Why two ACA environments instead of one

ACA environments require a **dedicated subnet** and represent a shared network/security boundary.

Using two environments gives us:
- isolation between **CI/CD** and **runtime workloads**,
- separate scaling/noise domains,
- cleaner RBAC and egress policy,
- ability to tighten runner egress differently from app egress.

## 4.3 Private DNS zones to create

At minimum:
- `privatelink.documents.azure.com` — Cosmos DB NoSQL
- `privatelink.blob.core.windows.net` — Blob Storage
- `privatelink.vaultcore.azure.net` — Key Vault
- `privatelink.openai.azure.com` — Azure OpenAI
- `privatelink.cognitiveservices.azure.com` — Document Intelligence / Azure AI services
- `privatelink.services.ai.azure.com` — Foundry service endpoints where applicable
- `privatelink.swedencentral.azurecontainerapps.io` — ACA environment private endpoint
- `privatelink.servicebus.windows.net` — Service Bus

Recommended additional zone if ACR is private:
- `privatelink.azurecr.io`
- `swedencentral.data.privatelink.azurecr.io`

## 4.4 NAT Gateway / egress guidance

For **ACA workload-profile environments**, Azure documents support **UDR and NAT Gateway** egress. That makes workload-profile environments the right choice here.

### Recommendation
- Put **NAT Gateway or Azure Firewall** on both ACA subnets.
- Do **not** attach NAT to the private-endpoint subnet.
- Use NAT if the goal is **stable outbound IPs** with low complexity.
- Use Azure Firewall if the goal is **FQDN allowlisting and inspection**.

### My recommendation for this project
- **Runner subnet:** prioritize **deterministic egress**. NAT Gateway is the minimum; Azure Firewall is better if Kiko wants explicit allowlists for GitHub/Microsoft endpoints.
- **App subnet:** if outbound is tightly controlled, prefer Azure Firewall or UDR-based central egress.

## 4.5 ACA internal vs external environment

| Environment mode | What it means | Fit here |
|---|---|---:|
| **Internal** | Ingress is reachable only from inside the VNet / connected private networks. | **Preferred** for app workloads. |
| External | Public ingress endpoint exists. | Not aligned with Kiko's private-only target. |

### Important nuance
If all callers already sit **inside the same VNet**, an **internal ACA environment** may be enough and an ACA Private Endpoint may be unnecessary for day-to-day east-west calls.

However, ACA **Private Endpoint** is useful when:
- clients live in a different VNet,
- hub/spoke DNS indirection is needed,
- private access from another network boundary is required.

---

## 5. Private Endpoint Compatibility Matrix

| Service | Private Endpoint Support | Sweden Central Availability | Notes |
|---|---|---|---|
| **Azure Cosmos DB (NoSQL)** | **Yes** | **Yes** | Private Link is GA for Cosmos DB in all public regions. For NoSQL use `privatelink.documents.azure.com`. Cosmos private endpoints allocate multiple IPs; multi-region/failover scenarios need careful DNS planning. |
| **Azure Blob Storage** | **Yes** | **Yes** | Storage private endpoints are GA in all public regions. Blob DNS zone: `privatelink.blob.core.windows.net`. Add `dfs` too if Data Lake Gen2 is enabled. |
| **Azure Key Vault** | **Yes** | **Yes** | Private Link is GA in all public regions. DNS zone: `privatelink.vaultcore.azure.net`. Disable public network access after PE + DNS validation. |
| **AI Foundry Agent Service** | **Yes, with caveats** | **Yes** | Foundry Agent Service private networking is supported and Sweden Central is supported. Major caveats: hosted-agent VNet injection must be set **at create time**, hosted-agent ACR **cannot** be private-only, and agent subnets must be dedicated. |
| **Azure OpenAI Service** | **Yes** | **Yes** | OpenAI supports private networking; use `privatelink.openai.azure.com`. Sweden Central is a supported Azure OpenAI region, but exact model availability still varies by model/SKU. |
| **Azure AI Document Intelligence / Content Understanding** | **Yes** | **Yes, with feature caveats** | Document Intelligence uses the Azure AI services private endpoint path (`privatelink.cognitiveservices.azure.com`). Sweden Central supports the service, but some model/build capabilities can be region-limited. Content Understanding is also available in Sweden Central, but preview/processing-location limits still apply depending on API mode. |
| **Azure Container Apps Environment** | **Yes, workload-profile env only** | **Yes** | ACA Private Endpoint is supported for workload-profile environments for Consumption and Dedicated plans; Microsoft documentation still labels ACA private endpoint support as **Public Preview** in the Private Link availability matrix. Internal environments may already satisfy same-VNet private access. DNS zone: `privatelink.swedencentral.azurecontainerapps.io`. |
| **Azure Service Bus** | **Yes** | **Yes** | Private Link is supported in all public regions, but **Premium tier only**. DNS zone: `privatelink.servicebus.windows.net`. |

---

## 6. Risks, Limitations, and Cost Impact

## 6.1 Hard technical limitations

### 1. ACA runners are not universal CI workers
This is the biggest limitation.
If the pipeline expects local Docker, service containers, or privileged build steps, ACA Jobs are the wrong pool.

### 2. GitHub is not private
Even with self-hosted private runners, you still need controlled outbound access to:
- `github.com`
- `api.github.com`
- GitHub Actions token endpoints
- package registries
- Microsoft control plane endpoints

If the architecture requirement is interpreted as **"no public egress at all"**, GitHub SaaS is incompatible.

### 3. Private DNS is the real failure point
Most private-endpoint deployments fail because of:
- missing zone links,
- custom DNS not forwarding to `168.63.129.16`,
- stale records after regional changes,
- split-horizon mistakes.

### 4. ACA networking gotchas
- Use **workload-profile environments**, not legacy consumption-only, because workload-profile environments support UDR/NAT and private endpoints.
- ACA reserves IPs internally; production designs should not size to the bare `/27` minimum.
- ACA private endpoint adds an extra **Dedicated Plan Management** billing line.

### 5. Foundry Agent Service gotchas
- Hosted-agent network injection must be decided **up front**.
- Hosted-agent ACR currently **cannot be behind a private endpoint with public access disabled**.
- Dedicated agent subnet per Foundry resource is required.

### 6. Document Intelligence gotchas
- Some Studio experiences require public Studio IP allowlisting (`20.3.165.95`) for certain features such as auto-labeling.
- Some feature/model build modes are region-dependent; Sweden Central is not always feature-parity with West Europe/East US.

### 7. Cosmos DB gotchas
- Private endpoints can reserve **multiple IPs per account**.
- Multi-region failover with private endpoints is more DNS-sensitive than the public-endpoint model.

## 6.2 Cost impact

Private networking is materially more expensive than public PaaS.
Main cost drivers:
- **Private Endpoint** per service/subresource
- **Private DNS zones** and zone links
- **NAT Gateway** or **Azure Firewall** egress
- **ACA private endpoint dedicated management charge**
- **Service Bus Premium** if Service Bus is selected
- potential separate **ACA environment for runners**

This cost is justified if Kiko's requirements are:
- private-only access to data services,
- deterministic egress,
- no reliance on public GitHub-hosted runners for private deployments.

---

## 7. Recommended Decision Set

1. **Adopt the phased bootstrap model.** It is the correct answer to the chicken-and-egg problem.
2. **Use ACA Jobs for self-hosted runners**, not ACA Apps.
3. **Create a dedicated runner ACA environment** separate from the application ACA environment.
4. **Use workload-profile ACA environments** only.
5. **Use controlled public egress** (NAT or Firewall). Do not promise full internet isolation while using GitHub SaaS.
6. **Keep Docker/image-build workloads off ACA runners** unless the workflow is redesigned around remote build services such as ACR Tasks.
7. **Treat private DNS as first-class IaC**, not as a post-deploy manual task.
8. **If Foundry hosted agents are adopted later, treat them as a separate exception path** because their ACR/private-networking constraints differ from the rest of the estate.

---

## 8. Source Notes

Key sources consulted:
- Microsoft Learn: **Tutorial: Deploy self-hosted CI/CD runners and agents with Azure Container Apps jobs**
- Microsoft Learn: **Jobs in Azure Container Apps**
- Microsoft Learn: **Networking in Azure Container Apps / custom virtual networks / private endpoints and DNS**
- Microsoft Learn: **Azure Private Link availability**
- Microsoft Learn: **Azure Private Endpoint private DNS zone values**
- Microsoft Learn: **Configure Azure OpenAI networking**
- Microsoft Learn: **Configure secure access with managed identities and virtual networks** (Document Intelligence)
- Microsoft Learn: **Set up private networking for Foundry Agent Service**
- Microsoft Learn / web checks for Sweden Central availability and current service caveats
