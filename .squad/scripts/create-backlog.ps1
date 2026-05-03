#!/usr/bin/env pwsh
# Verdecora — Full project backlog creation script
# Run with an account that has write/admin access to frdeange/verdecoraTest.
# Idempotent: gh label create uses --force; gh issue create will create duplicates only if rerun.
# Usage:  pwsh -File .squad\scripts\create-backlog.ps1

$ErrorActionPreference = 'Stop'
$repo = 'frdeange/verdecoraTest'

Write-Host "==> Creating labels..." -ForegroundColor Cyan
& "$PSScriptRoot\create-labels.ps1"

function New-Issue {
    param(
        [string]$Title,
        [string]$Body,
        [string[]]$Labels
    )
    $labelArg = ($Labels -join ',')
    $url = gh issue create --repo $repo --title $Title --body $Body --label $labelArg 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Failed: $Title -> $url"
        return $null
    }
    # Extract issue number from URL (last path segment)
    $num = ($url -split '/')[-1]
    Write-Host ("#{0,-3} {1}" -f $num, $Title)
    return [int]$num
}

# Track issue numbers so dependencies can be wired
$ids = @{}

# ============================================================
# SPRINT 0 — Foundation & Validation
# ============================================================
$body = @'
## Description

Validate Microsoft Agent Framework v1.0 patterns end-to-end in Azure Container Apps before committing to the architecture.

Build a minimal pipeline using `SequentialBuilder` and `HandoffBuilder` with **3 stub agents** (mock A1 → A2 → A3) and run it inside an ACA app. Verify state passing, error propagation, observability hooks, and graceful shutdown.

## Acceptance Criteria

- [ ] 3 stub agents defined with MAF v1.0 SDK (Python)
- [ ] `SequentialBuilder` chain executes successfully
- [ ] `HandoffBuilder` handoff between two stubs works (with reason capture)
- [ ] Deployed to ACA dev environment
- [ ] OTel traces visible in App Insights
- [ ] Failure in middle agent surfaces correctly
- [ ] PoC report committed to `docs/poc/maf-v1-poc.md`

## Agent
Ash (Architecture Lead)

## Dependencies
None — this unblocks Sprint 1.
'@
$ids['s0-poc-maf'] = New-Issue `
  -Title "🔬 [S0] MAF v1.0 PoC in Azure Container Apps" `
  -Body $body `
  -Labels @('squad:ash','🔬 poc','priority:critical','phase:foundation','🤖 ai-agents','⚡ parallelizable')

$body = @'
## Description

Validate the **native Business Central MCP** against the CRONUS demo company. Confirm that read operations (Purchase Order, Vendor, Item) and the write operation (Posted Purchase Receipt) work as documented.

## Acceptance Criteria

- [ ] BC MCP connected to CRONUS sandbox
- [ ] Read PO header + lines by number
- [ ] Read Vendor by No.
- [ ] Read Item by No. (incl. unit conversions)
- [ ] Write a Posted Purchase Receipt and confirm idempotency key behaviour
- [ ] Latency + error matrix documented in `docs/poc/bc-mcp-validation.md`

## Agent
Burke (BC/ERP Integration)

## Dependencies
None.
'@
$ids['s0-bc-mcp'] = New-Issue `
  -Title "📊 [S0] BC MCP validation against CRONUS" `
  -Body $body `
  -Labels @('squad:burke','🔬 poc','priority:critical','phase:foundation','🔌 mcp','⚡ parallelizable')

$body = @'
## Description

Send a templated HITL email through Azure Communication Services Email with action buttons (Accept / Reject / Modify) that callback to a webhook. Validate deliverability, link signing, and end-to-end roundtrip.

## Acceptance Criteria

- [ ] ACS Email resource provisioned in dev
- [ ] Sender domain verified (or Azure-managed domain used)
- [ ] Test email with 3 action buttons received in Outlook + Gmail
- [ ] Callback received by stub webhook with signed payload
- [ ] Token TTL + replay protection considered (note in PoC report)
- [ ] Report at `docs/poc/acs-email-poc.md`

## Agent
Newt (Communications/HITL)
'@
$ids['s0-acs-poc'] = New-Issue `
  -Title "🔌 [S0] ACS Email PoC with HITL action buttons" `
  -Body $body `
  -Labels @('squad:newt','🔬 poc','priority:high','phase:foundation','🔧 backend','⚡ parallelizable')

$body = @'
## Description

Bootstrap the network foundation: Hub VNet, dev subnets (ACA, PE, Runners), ACA environment (internal), and a self-hosted GitHub Actions runner deployed as an **ACA Job** so CI/CD can reach private endpoints later.

## Acceptance Criteria

- [ ] VNet + subnets provisioned (Bicep)
- [ ] ACA environment (workload profile) deployed in VNet
- [ ] Runner ACA Job registered against `frdeange/verdecoraTest` with label `self-hosted-aca`
- [ ] Sample workflow runs on self-hosted runner
- [ ] NSGs + route tables documented

## Agent
Brett (Networking/Runners)
'@
$ids['s0-vnet-runners'] = New-Issue `
  -Title "🔐 [S0] VNet + self-hosted runners bootstrap" `
  -Body $body `
  -Labels @('squad:brett','☁️ infrastructure','priority:critical','phase:foundation','⚡ parallelizable')

$body = @'
## Description

Author the **base Bicep modules** consumed by every later sprint: resource group scaffolding, VNet, Service Bus namespace, Cosmos DB account, Blob Storage, Key Vault. Each module must be parameterized for dev/test/prod and ship with a smoke-test deployment.

## Acceptance Criteria

- [ ] `infra/modules/network.bicep`
- [ ] `infra/modules/servicebus.bicep` (queues + topics placeholders)
- [ ] `infra/modules/cosmos.bicep` (SQL API, autoscale)
- [ ] `infra/modules/storage.bicep` (Blob containers)
- [ ] `infra/modules/keyvault.bicep` (RBAC mode, soft-delete, purge protection)
- [ ] Dev environment deployment green via `what-if` + `deploy`
- [ ] Module README per module

## Agent
Dallas (IaC/Bicep)

## Dependencies
- VNet design from #$($ids['s0-vnet-runners'])
'@
$ids['s0-bicep-base'] = New-Issue `
  -Title "☁️ [S0] Bicep foundation modules" `
  -Body $body `
  -Labels @('squad:dallas','☁️ infrastructure','priority:critical','phase:foundation','🔗 sequential')

$body = @'
## Description

Define the identity model: one **User-Assigned Managed Identity per ACA app/job**, RBAC role assignments (least privilege) on Cosmos, Service Bus, Storage, Key Vault, ACS, and the BC MCP host. Centralize role definitions in Bicep.

## Acceptance Criteria

- [ ] UAMIs declared in Bicep
- [ ] Role assignment matrix documented in `docs/security/identity-matrix.md`
- [ ] Key Vault access via RBAC (no access policies)
- [ ] No secrets in code/config — Key Vault references only
- [ ] Identity smoke-test from a sample container

## Agent
Lambert (Identity/Security)

## Dependencies
- #$($ids['s0-bicep-base'])
'@
$ids['s0-identity'] = New-Issue `
  -Title "🔒 [S0] Identity foundation — Managed Identities + RBAC" `
  -Body $body `
  -Labels @('squad:lambert','🔒 security','priority:critical','phase:foundation','🔗 sequential')

$body = @'
## Description

Benchmark **Azure AI Content Understanding** vs **Document Intelligence** on 50+ real albaranes. Measure extraction accuracy (header + line items), latency, cost, and resilience to noisy scans / handwritten notes. Output a recommendation.

## Acceptance Criteria

- [ ] Sample set of ≥50 albaranes (anonymized) curated
- [ ] Both services invoked through identical pipeline
- [ ] Field-level F1 score per service
- [ ] Latency p50/p95 + cost per 1000 docs
- [ ] Decision recorded in `docs/poc/extraction-benchmark.md`
- [ ] ADR updated if recommendation differs from current default

## Agent
Bishop (AI Agents) + Ash (Architecture)
'@
$ids['s0-cu-bench'] = New-Issue `
  -Title "🤖 [S0] Content Understanding vs Document Intelligence benchmark" `
  -Body $body `
  -Labels @('squad:bishop','🔬 poc','priority:high','phase:foundation','🤖 ai-agents','⚡ parallelizable')

$body = @'
## Description

Harden the GitHub Actions setup: branch protection on `main`, required checks, signed commits optional, integration with the self-hosted ACA runner, OIDC federation to Azure (no long-lived secrets), and reusable workflow templates for Python services and Bicep deployments.

## Acceptance Criteria

- [ ] Branch protection on `main` (PR required, status checks, linear history)
- [ ] OIDC federation to Azure subscription configured
- [ ] Reusable workflow `.github/workflows/python-service.yml`
- [ ] Reusable workflow `.github/workflows/bicep-deploy.yml`
- [ ] Self-hosted runner used for jobs needing VNet egress
- [ ] CODEOWNERS file

## Agent
Hicks (DevOps Lead)

## Dependencies
- #$($ids['s0-vnet-runners'])
'@
$ids['s0-cicd'] = New-Issue `
  -Title "⚙️ [S0] CI/CD pipeline hardening" `
  -Body $body `
  -Labels @('squad:hicks','☁️ infrastructure','priority:high','phase:foundation','🔗 sequential')

$body = @'
## Description

Stand up the project-wide test framework: pytest layout, shared fixtures, BC MCP mocks, Cosmos test container, Service Bus emulator hooks, coverage gates.

## Acceptance Criteria

- [ ] `tests/` layout (unit / integration / e2e)
- [ ] `conftest.py` with shared fixtures
- [ ] BC MCP mock fixtures (PO/Vendor/Item)
- [ ] Coverage gate ≥ 80% wired into CI
- [ ] Sample failing + passing test in each layer

## Agent
Vasquez (QA/Testing)

## Dependencies
- #$($ids['s0-cicd'])
'@
$ids['s0-test-fw'] = New-Issue `
  -Title "🧪 [S0] Test framework setup (pytest + fixtures + BC mocks)" `
  -Body $body `
  -Labels @('squad:vasquez','🧪 testing','priority:high','phase:foundation','🔗 sequential')

# ============================================================
# SPRINT 1 — Core Agents (A1 + A2 + A3)
# ============================================================
$body = @'
## Description

Implement **A1 Extractor**: MAF agent that consumes a PDF/image of an albarán, calls Content Understanding (or DI per benchmark) for layout, then GPT-5.1 with strict JSON-schema output for normalized line items.

## Acceptance Criteria

- [ ] MAF agent class in `src/agents/a1_extractor/`
- [ ] Strict JSON schema (header + lines) enforced via response format
- [ ] Confidence score per field
- [ ] Retries + fallback to DI if Content Understanding fails
- [ ] OTel spans + token-usage metrics
- [ ] Prompts in `src/agents/a1_extractor/prompts/` (versioned)

## Agent
Bishop (AI Agents)

## Dependencies
- #$($ids['s0-poc-maf']), #$($ids['s0-cu-bench'])
'@
$ids['s1-a1'] = New-Issue `
  -Title "🤖 [S1] A1 Extractor agent — MAF + Content Understanding + GPT-5.1" `
  -Body $body `
  -Labels @('squad:bishop','🤖 ai-agents','priority:high','phase:implementation','🔗 sequential')

$body = @'
## Description

Implement **A2 Triage**: lightweight MAF agent (GPT-5-mini) that classifies the extracted albarán and routes to the next stage. Reads triage policy from `feature-flags-mcp`.

## Acceptance Criteria

- [ ] Structured output: `{route, reason, confidence}`
- [ ] Reads policy thresholds from feature flags
- [ ] Deterministic for given input (temperature=0)
- [ ] Unit tests cover all routing branches
- [ ] Prompt versioned

## Agent
Bishop (AI Agents)

## Dependencies
- #$($ids['s1-a1']), #$($ids['s1-feature-flags-mcp'] = 0; 0)
'@
$ids['s1-a2'] = New-Issue `
  -Title "🤖 [S1] A2 Triage agent — GPT-5-mini structured routing" `
  -Body $body `
  -Labels @('squad:bishop','🤖 ai-agents','priority:high','phase:implementation','🔗 sequential')

$body = @'
## Description

Implement **A3 Coherence**: cross-references the extracted albarán with BC (PO, Vendor, Item) via BC MCP read tools and runs sanity checks (vendor match, item existence, PO open/closed, quantity sanity).

## Acceptance Criteria

- [ ] Calls BC MCP read tools (PO, Vendor, Item)
- [ ] Sanity-check rules pluggable
- [ ] Emits a structured `coherence_report` with per-line verdicts
- [ ] Handles missing PO / unknown item gracefully
- [ ] Telemetry on each BC call

## Agent
Bishop (AI Agents)

## Dependencies
- #$($ids['s1-a1']), #$($ids['s0-bc-mcp'])
'@
$ids['s1-a3'] = New-Issue `
  -Title "🤖 [S1] A3 Coherence agent — GPT-5-mini + BC MCP read" `
  -Body $body `
  -Labels @('squad:bishop','🤖 ai-agents','priority:high','phase:implementation','🔗 sequential')

$body = @'
## Description

Build a Python MCP server exposing Cosmos DB read+write tools used by the agents (albaran state, dedup keys, audit trail). Auth via Managed Identity.

## Acceptance Criteria

- [ ] MCP tools: `get_albaran`, `upsert_albaran`, `query_by_dedup_key`, `append_audit`
- [ ] Pydantic schemas + JSON-schema for MCP tool spec
- [ ] Backed by `azure-cosmos` SDK with token credential
- [ ] Container image + ACA app deploy
- [ ] Integration tests against Cosmos emulator

## Agent
Parker (MCP/Backend)
'@
$ids['s1-cosmos-mcp'] = New-Issue `
  -Title "🔌 [S1] cosmos-mcp server — Python MCP for Cosmos R/W" `
  -Body $body `
  -Labels @('squad:parker','🔌 mcp','priority:high','phase:implementation','⚡ parallelizable')

$body = @'
## Description

Python MCP server wrapping Azure AI Content Understanding (and DI fallback) so agents access extraction through a uniform tool surface.

## Acceptance Criteria

- [ ] MCP tools: `analyze_document`, `get_layout`, `get_fields`
- [ ] Streaming + retries
- [ ] Per-document timing telemetry
- [ ] Container image + ACA app
- [ ] Unit tests with sample PDFs

## Agent
Parker (MCP/Backend)

## Dependencies
- #$($ids['s0-cu-bench'])
'@
$ids['s1-cu-mcp'] = New-Issue `
  -Title "🔌 [S1] content-understanding-mcp server" `
  -Body $body `
  -Labels @('squad:parker','🔌 mcp','priority:high','phase:implementation','🔗 sequential')

$body = @'
## Description

Cosmos-backed feature-flag / triage-policy MCP server. Hot-reloadable thresholds (tolerance, routing rules, kill switches) without redeploy.

## Acceptance Criteria

- [ ] MCP tools: `get_flag`, `get_policy`, `set_flag` (admin only)
- [ ] Cosmos container `feature-flags` with versioning
- [ ] In-memory cache with TTL
- [ ] Unit + integration tests

## Agent
Parker (MCP/Backend)
'@
$ids['s1-ff-mcp'] = New-Issue `
  -Title "🔌 [S1] feature-flags-mcp server (Cosmos-backed)" `
  -Body $body `
  -Labels @('squad:parker','🔌 mcp','priority:medium','phase:implementation','⚡ parallelizable')

$body = @'
## Description

Unit + integration tests for A1: schema validation, low-confidence handling, fallback path, prompt regression suite.

## Acceptance Criteria
- [ ] ≥ 90% unit coverage on A1 module
- [ ] Integration test against Content Understanding sandbox (10 docs)
- [ ] Prompt regression with golden fixtures
- [ ] Negative tests (corrupt PDF, empty image)

## Agent
Vasquez (QA)

## Dependencies
- #$($ids['s1-a1'])
'@
$ids['s1-a1-tests'] = New-Issue `
  -Title "🧪 [S1] A1 Extractor tests (unit + integration)" `
  -Body $body `
  -Labels @('squad:vasquez','🧪 testing','priority:high','phase:implementation','🔗 sequential')

$body = @'
## Description
Unit tests covering every routing branch and policy scenario for A2.

## Acceptance Criteria
- [ ] All routes covered
- [ ] Policy hot-reload simulated
- [ ] Determinism asserted

## Agent
Vasquez (QA)

## Dependencies
- #$($ids['s1-a2'])
'@
$ids['s1-a2-tests'] = New-Issue `
  -Title "🧪 [S1] A2 Triage tests (unit)" `
  -Body $body `
  -Labels @('squad:vasquez','🧪 testing','priority:medium','phase:implementation','🔗 sequential')

$body = @'
## Description
Unit + integration tests against BC MCP mocks for A3.

## Acceptance Criteria
- [ ] All sanity rules tested
- [ ] BC MCP mock-driven integration scenarios
- [ ] Failure modes: missing PO, vendor mismatch, item not found

## Agent
Vasquez (QA)

## Dependencies
- #$($ids['s1-a3'])
'@
$ids['s1-a3-tests'] = New-Issue `
  -Title "🧪 [S1] A3 Coherence tests (unit + integration)" `
  -Body $body `
  -Labels @('squad:vasquez','🧪 testing','priority:high','phase:implementation','🔗 sequential')

$body = @'
## Description

Bicep modules to provision Azure OpenAI (or AI Foundry project) with **GPT-5.1** and **GPT-5-mini** model deployments, capacity, and content-filter policy. Diagnostic settings to Log Analytics.

## Acceptance Criteria
- [ ] `infra/modules/openai.bicep`
- [ ] Deployments parametrized per env
- [ ] Quotas requested + tracked
- [ ] PE-ready (gated on Sprint 4)

## Agent
Dallas (IaC)
'@
$ids['s1-aoai-bicep'] = New-Issue `
  -Title "☁️ [S1] Bicep — Azure OpenAI + Foundry project + model deployments" `
  -Body $body `
  -Labels @('squad:dallas','☁️ infrastructure','priority:high','phase:implementation','⚡ parallelizable')

$body = @'
## Description
Author agent specifications and prompt docs for A1, A2, A3.

## Acceptance Criteria
- [ ] `docs/agents/a1-extractor.md`
- [ ] `docs/agents/a2-triage.md`
- [ ] `docs/agents/a3-coherence.md`
- [ ] Prompt change log

## Agent
Hudson (Tech Writer)

## Dependencies
- #$($ids['s1-a1']), #$($ids['s1-a2']), #$($ids['s1-a3'])
'@
$ids['s1-docs'] = New-Issue `
  -Title "📝 [S1] A1–A3 technical docs + prompt documentation" `
  -Body $body `
  -Labels @('squad:hudson','📝 documentation','priority:medium','phase:implementation','🔗 sequential')

# ============================================================
# SPRINT 2 — Validation + Inventory (A4 + A5) + Pipeline
# ============================================================
$body = @'
## Description
Compare extracted albarán lines vs PO lines at 2% quantity tolerance (configurable via feature flags). Emits per-line verdicts and a global decision.

## Acceptance Criteria
- [ ] Tolerance + rounding rules configurable
- [ ] Per-line `ok|over|under|missing|extra` verdicts
- [ ] Global decision: `auto-approve | hitl | reject`
- [ ] Deterministic; unit tests pin behaviour

## Agent
Bishop (AI Agents)

## Dependencies
- #$($ids['s1-a3'])
'@
$ids['s2-a4'] = New-Issue `
  -Title "🤖 [S2] A4 Validator agent — line-level comparison @ 2% tolerance" `
  -Body $body `
  -Labels @('squad:bishop','🤖 ai-agents','priority:high','phase:implementation','🔗 sequential')

$body = @'
## Description
Posts the Purchase Receipt to BC via BC MCP write. Idempotent (uses dedup key as `External Document No.`). `require_approval` flag honoured.

## Acceptance Criteria
- [ ] Idempotency verified (replay safe)
- [ ] `require_approval=true` path blocks until HITL approves
- [ ] Compensation/rollback playbook documented
- [ ] Telemetry on each BC write

## Agent
Bishop (AI Agents)

## Dependencies
- #$($ids['s2-a4']), #$($ids['s0-bc-mcp'])
'@
$ids['s2-a5'] = New-Issue `
  -Title "🤖 [S2] A5 Inventory agent — Post Purchase Receipt via BC MCP" `
  -Body $body `
  -Labels @('squad:bishop','🤖 ai-agents','priority:critical','phase:implementation','🔗 sequential')

$body = @'
## Description
Configure native BC MCP for both **read** (PO/Vendor/Item) and **write** (Posted Purchase Receipt) configurations and wire to agents.

## Acceptance Criteria
- [ ] Connection profiles per env
- [ ] Auth via Entra ID + MI
- [ ] Tool allow-list documented
- [ ] Smoke test from ACA app

## Agent
Burke (BC/ERP)

## Dependencies
- #$($ids['s0-bc-mcp'])
'@
$ids['s2-bc-mcp'] = New-Issue `
  -Title "🔌 [S2] bc-mcp integration — read + write configs" `
  -Body $body `
  -Labels @('squad:burke','🔌 mcp','priority:critical','phase:implementation','🔗 sequential')

$body = @'
## Description
The orchestrator ACA app: composes A1→A2→A3→A4→A5 with `SequentialBuilder`+`HandoffBuilder`. Consumes Service Bus, persists state in Cosmos, emits domain events.

## Acceptance Criteria
- [ ] Pipeline runs end-to-end on happy path
- [ ] Handoff to HITL branch on validator decision
- [ ] Idempotent restart from last checkpoint
- [ ] Health + readiness probes
- [ ] OTel end-to-end trace

## Agent
Parker (MCP/Backend)

## Dependencies
- #$($ids['s1-a1']), #$($ids['s1-a2']), #$($ids['s1-a3']), #$($ids['s2-a4']), #$($ids['s2-a5'])
'@
$ids['s2-orchestrator'] = New-Issue `
  -Title "🔧 [S2] agentic-orchestrator ACA app — MAF Sequential+Handoff (A1→A5)" `
  -Body $body `
  -Labels @('squad:parker','🔧 backend','priority:critical','phase:implementation','🔗 sequential')

$body = @'
## Description
ACA Job triggered by Event Grid (Blob Created). Computes dedup key (hash of file + metadata), checks Cosmos, enqueues to Service Bus only if new.

## Acceptance Criteria
- [ ] Dedup key spec documented
- [ ] At-least-once semantics with idempotent dedup
- [ ] Poison-message handling (DLQ)
- [ ] Metrics: dedup ratio, lag

## Agent
Parker (MCP/Backend)
'@
$ids['s2-flow0'] = New-Issue `
  -Title "🔧 [S2] Flow 0 dedup ACA Job — Event Grid → Service Bus → Cosmos" `
  -Body $body `
  -Labels @('squad:parker','🔧 backend','priority:high','phase:implementation','⚡ parallelizable')

$body = @'
## Description
Unit + integration tests for validator logic, inventory idempotency, and the full A1→A5 handoff chain.

## Acceptance Criteria
- [ ] Tolerance edge cases covered
- [ ] Replay/idempotency proven for A5
- [ ] Handoff chain test with stub BC

## Agent
Vasquez (QA)

## Dependencies
- #$($ids['s2-a4']), #$($ids['s2-a5'])
'@
$ids['s2-tests'] = New-Issue `
  -Title "🧪 [S2] A4–A5 tests + handoff chain" `
  -Body $body `
  -Labels @('squad:vasquez','🧪 testing','priority:high','phase:implementation','🔗 sequential')

$body = @'
## Description
End-to-end happy-path test: blob upload → dedup → orchestrator → BC write. Uses CRONUS sandbox.

## Acceptance Criteria
- [ ] Automated in CI (nightly)
- [ ] Asserts BC posted receipt exists
- [ ] Trace correlation across all hops

## Agent
Vasquez (QA)

## Dependencies
- #$($ids['s2-orchestrator']), #$($ids['s2-flow0'])
'@
$ids['s2-e2e'] = New-Issue `
  -Title "🧪 [S2] E2E pipeline test — Flow 0 → Flow 1+2 happy path" `
  -Body $body `
  -Labels @('squad:vasquez','🧪 testing','priority:high','phase:implementation','🔗 sequential')

$body = @'
## Description
Bicep for all ACA apps and jobs (orchestrator, MCP servers, Flow 0 job) with KEDA scalers (Service Bus length, HTTP concurrency).

## Acceptance Criteria
- [ ] Per-app module
- [ ] KEDA scaler rules per workload
- [ ] Min/max replica policy per env
- [ ] Diagnostic settings wired

## Agent
Dallas (IaC)
'@
$ids['s2-bicep-aca'] = New-Issue `
  -Title "☁️ [S2] Bicep — Container Apps + ACA Jobs + KEDA scalers" `
  -Body $body `
  -Labels @('squad:dallas','☁️ infrastructure','priority:high','phase:implementation','⚡ parallelizable')

$body = @'
## Description
Document A4, A5, orchestrator pipeline, Flow 0 dedup.

## Acceptance Criteria
- [ ] Agent specs for A4, A5
- [ ] Pipeline diagram + failure modes
- [ ] Operations notes

## Agent
Hudson (Tech Writer)

## Dependencies
- #$($ids['s2-a4']), #$($ids['s2-a5']), #$($ids['s2-orchestrator'])
'@
$ids['s2-docs'] = New-Issue `
  -Title "📝 [S2] A4–A5 + pipeline docs" `
  -Body $body `
  -Labels @('squad:hudson','📝 documentation','priority:medium','phase:implementation','🔗 sequential')

# ============================================================
# SPRINT 3 — Communication (A6) + HITL
# ============================================================
$body = @'
## Description
Event-driven MAF agent that sends HITL emails (and confirmations / escalations) using templated bodies through ACS Email MCP.

## Acceptance Criteria
- [ ] Templates versioned in repo
- [ ] Locale support (es-ES first)
- [ ] Reacts to domain events (discrepancy, escalation, resolved)
- [ ] Audit-logged in Cosmos

## Agent
Bishop (AI Agents)

## Dependencies
- #$($ids['s2-a4'])
'@
$ids['s3-a6'] = New-Issue `
  -Title "🤖 [S3] A6 Communication agent — event-driven, ACS Email, templates" `
  -Body $body `
  -Labels @('squad:bishop','🤖 ai-agents','priority:high','phase:hitl','🔗 sequential')

$body = @'
## Description
Python MCP server wrapping ACS Email send + signed-link generation.

## Acceptance Criteria
- [ ] MCP tools: `send_email`, `generate_action_link`
- [ ] Link signing (HMAC) + TTL
- [ ] Bounce/complaint handling

## Agent
Parker (MCP/Backend)

## Dependencies
- #$($ids['s0-acs-poc'])
'@
$ids['s3-acs-mcp'] = New-Issue `
  -Title "🔌 [S3] acs-email-mcp server" `
  -Body $body `
  -Labels @('squad:parker','🔌 mcp','priority:high','phase:hitl','🔗 sequential')

$body = @'
## Description
FastAPI web form for HITL decisions. Auth via Entra ID. Renders the albarán + PDF link, allows Accept / Reject / Modify with reason and per-line edits.

## Acceptance Criteria
- [ ] Entra ID auth (store managers group)
- [ ] Signed action links from email landing here
- [ ] Modifications persisted back to Cosmos
- [ ] CSRF + replay protection
- [ ] Mobile-friendly

## Agent
Parker (MCP/Backend)

## Dependencies
- #$($ids['s3-acs-mcp'])
'@
$ids['s3-webform'] = New-Issue `
  -Title "🔧 [S3] hitl-webform ACA app — FastAPI accept/reject/modify" `
  -Body $body `
  -Labels @('squad:parker','🔧 backend','priority:high','phase:hitl','🔗 sequential')

$body = @'
## Description
Use Service Bus scheduled messages to drive HITL escalations at 24h / 48h / 72h with cancellation when the case resolves.

## Acceptance Criteria
- [ ] Scheduled message dispatcher
- [ ] Cancellation tokens stored with case
- [ ] Configurable per supplier/store

## Agent
Parker (MCP/Backend)
'@
$ids['s3-sb-timer'] = New-Issue `
  -Title "🔧 [S3] Service Bus timer integration — 24h/48h/72h escalation" `
  -Body $body `
  -Labels @('squad:parker','🔧 backend','priority:medium','phase:hitl','⚡ parallelizable')

$body = @'
## Description
Tests covering email send, signed-link callback, timer escalation, and cancellation on resolution.

## Acceptance Criteria
- [ ] Token tampering rejected
- [ ] Replay rejected
- [ ] Timer cancellation verified

## Agent
Vasquez (QA)

## Dependencies
- #$($ids['s3-webform']), #$($ids['s3-sb-timer'])
'@
$ids['s3-hitl-tests'] = New-Issue `
  -Title "🧪 [S3] HITL flow tests — email, callback, escalation, cancellation" `
  -Body $body `
  -Labels @('squad:vasquez','🧪 testing','priority:high','phase:hitl','🔗 sequential')

$body = @'
## Description
End-to-end test: induced discrepancy triggers HITL, manager approves via email/webform, A5 posts to BC.

## Acceptance Criteria
- [ ] Runs in nightly CI
- [ ] Asserts BC posting after approval
- [ ] Asserts no posting when rejected

## Agent
Vasquez (QA)

## Dependencies
- #$($ids['s3-a6']), #$($ids['s3-webform'])
'@
$ids['s3-e2e-hitl'] = New-Issue `
  -Title "🧪 [S3] E2E with HITL — discrepancy → email → approval → inventory" `
  -Body $body `
  -Labels @('squad:vasquez','🧪 testing','priority:high','phase:hitl','🔗 sequential')

$body = @'
## Description
Provision ACS Email + Communication Services + sender domain (or Azure-managed). DNS records (SPF/DKIM/DMARC) automated where possible.

## Acceptance Criteria
- [ ] ACS resources in Bicep
- [ ] DNS records doc (or DNS zone module)
- [ ] Verified-domain output

## Agent
Dallas (IaC)
'@
$ids['s3-bicep-acs'] = New-Issue `
  -Title "☁️ [S3] Bicep — ACS Email resource + sender domain DNS" `
  -Body $body `
  -Labels @('squad:dallas','☁️ infrastructure','priority:high','phase:hitl','⚡ parallelizable')

$body = @'
## Description
Lock down HITL: Entra ID for webform, time-limited SAS for PDF preview links, full audit trail in Cosmos (who decided what, when, from where).

## Acceptance Criteria
- [ ] Entra ID app reg with right scopes
- [ ] SAS TTL ≤ 15 min, IP-bound where possible
- [ ] Immutable audit append in Cosmos
- [ ] Threat model doc

## Agent
Lambert (Security)

## Dependencies
- #$($ids['s3-webform'])
'@
$ids['s3-hitl-sec'] = New-Issue `
  -Title "🔒 [S3] HITL security — Entra auth, SAS for PDFs, audit logging" `
  -Body $body `
  -Labels @('squad:lambert','🔒 security','priority:critical','phase:hitl','🔗 sequential')

$body = @'
## Description
End-user guide for store managers handling HITL cases.

## Acceptance Criteria
- [ ] Step-by-step screenshots
- [ ] FAQ
- [ ] es-ES + en-US versions

## Agent
Hudson (Tech Writer)

## Dependencies
- #$($ids['s3-webform'])
'@
$ids['s3-user-manual'] = New-Issue `
  -Title "📝 [S3] HITL user manual for store managers" `
  -Body $body `
  -Labels @('squad:hudson','📝 documentation','priority:medium','phase:hitl','🔗 sequential')

# ============================================================
# SPRINT 4 — Security, Observability, Hardening
# ============================================================
$body = @'
## Description
Apply Private Endpoints to every PaaS resource (Cosmos, Storage, Key Vault, Service Bus, ACS, Azure OpenAI, ACR). Disable public network access where possible. Update DNS via Private DNS zones.

## Acceptance Criteria
- [ ] PEs declared in Bicep for every PaaS
- [ ] Private DNS zones linked to VNet
- [ ] Public access disabled where supported
- [ ] Connectivity smoke tests green

## Agent
Brett (Networking)
'@
$ids['s4-pe'] = New-Issue `
  -Title "🔒 [S4] Private Endpoints for all PaaS services" `
  -Body $body `
  -Labels @('squad:brett','🔒 security','priority:critical','phase:hardening','⚡ parallelizable')

$body = @'
## Description
Add deterministic egress via NAT Gateway (or Azure Firewall) for ACA workload subnet. Restrict outbound to allow-list (Azure OpenAI, ACS, BC endpoints).

## Acceptance Criteria
- [ ] NAT GW or AzFW deployed in Bicep
- [ ] Egress allow-list documented
- [ ] Logs to Log Analytics

## Agent
Brett (Networking)
'@
$ids['s4-egress'] = New-Issue `
  -Title "🔒 [S4] NAT Gateway / Azure Firewall — egress control" `
  -Body $body `
  -Labels @('squad:brett','🔒 security','priority:high','phase:hardening','⚡ parallelizable')

$body = @'
## Description
Integrate Azure AI Content Safety on inbound text + OCR output, add structural prompt-injection mitigations (tool allow-listing, role separation, output schemas), and sanitize OCR text before LLM exposure.

## Acceptance Criteria
- [ ] Content Safety check on extracted text
- [ ] Output schema enforced for every agent
- [ ] Sanitization rules unit-tested
- [ ] Red-team test cases

## Agent
Lambert (Security)
'@
$ids['s4-prompt-injection'] = New-Issue `
  -Title "🔒 [S4] Prompt injection defense + Content Safety + OCR sanitization" `
  -Body $body `
  -Labels @('squad:lambert','🔒 security','priority:critical','phase:hardening','⚡ parallelizable')

$body = @'
## Description
Redact PII (driver/transportista names, handwritten signatures) from stored artifacts. Keep originals in restricted container with stricter RBAC.

## Acceptance Criteria
- [ ] Redaction pipeline integrated
- [ ] Two-tier storage (raw vs redacted)
- [ ] Access reviewed quarterly (doc)
- [ ] DPIA notes updated

## Agent
Lambert (Security)
'@
$ids['s4-pii'] = New-Issue `
  -Title "🔒 [S4] PII redaction — transportista names + signature regions" `
  -Body $body `
  -Labels @('squad:lambert','🔒 security','priority:high','phase:hardening','⚡ parallelizable')

$body = @'
## Description
Build dashboards for pipeline KPIs (throughput, p95 latency, auto-approve rate, HITL rate, BC errors, token cost per albarán).

## Acceptance Criteria
- [ ] Workbook JSON committed to repo
- [ ] KQL library in `ops/kql/`
- [ ] Dashboard linked from README

## Agent
Dallas (IaC) + observability-focused
'@
$ids['s4-dashboards'] = New-Issue `
  -Title "📊 [S4] Observability dashboards — App Insights, Workbooks, KQL" `
  -Body $body `
  -Labels @('squad:dallas','📊 observability','priority:high','phase:hardening','⚡ parallelizable')

$body = @'
## Description
Action-group + alert rules for: error rate >2%, Service Bus active messages > N, BC write failures, HITL cases pending > 24h.

## Acceptance Criteria
- [ ] Rules in Bicep
- [ ] Action group with email + webhook (Teams)
- [ ] Severity levels documented

## Agent
Dallas (IaC)
'@
$ids['s4-alerts'] = New-Issue `
  -Title "📊 [S4] Alerting rules — error rate, queue depth, BC failures, HITL backlog" `
  -Body $body `
  -Labels @('squad:dallas','📊 observability','priority:high','phase:hardening','⚡ parallelizable')

$body = @'
## Description
Automated security tests: prompt injection corpus, signed-link tampering, auth bypass attempts, RBAC negative tests.

## Acceptance Criteria
- [ ] Corpus in `tests/security/`
- [ ] Run nightly
- [ ] Findings auto-filed as issues

## Agent
Vasquez (QA)
'@
$ids['s4-sec-tests'] = New-Issue `
  -Title "🧪 [S4] Security testing — prompt injection + auth bypass" `
  -Body $body `
  -Labels @('squad:vasquez','🧪 testing','priority:high','phase:hardening','⚡ parallelizable')

$body = @'
## Description
Simulate 750 albaranes/day (peak burst 3x) using Azure Load Testing. Validate scaling, cost, and SLA.

## Acceptance Criteria
- [ ] Test plan in repo
- [ ] Results report with p95/p99
- [ ] Cost projection refreshed

## Agent
Vasquez (QA)
'@
$ids['s4-load'] = New-Issue `
  -Title "🧪 [S4] Load testing — 750 albaranes/day simulation" `
  -Body $body `
  -Labels @('squad:vasquez','🧪 testing','priority:high','phase:hardening','⚡ parallelizable')

$body = @'
## Description
Runbook for on-call: monitoring map, alert response, troubleshooting trees, rollback procedures.

## Acceptance Criteria
- [ ] `docs/ops/runbook.md`
- [ ] Reviewed by Hicks + Brett
- [ ] Linked from alert payloads

## Agent
Hudson (Tech Writer)
'@
$ids['s4-runbook'] = New-Issue `
  -Title "📝 [S4] Operations runbook" `
  -Body $body `
  -Labels @('squad:hudson','📝 documentation','priority:high','phase:hardening','⚡ parallelizable')

$body = @'
## Description
Config reference: tolerance thresholds, feature flags, MCP endpoints, BC company/profile setup, env matrix.

## Acceptance Criteria
- [ ] `docs/ops/configuration.md`
- [ ] Cross-referenced from ADR

## Agent
Hudson (Tech Writer)
'@
$ids['s4-config-guide'] = New-Issue `
  -Title "📝 [S4] Configuration guide — thresholds, MCP config, BC setup" `
  -Body $body `
  -Labels @('squad:hudson','📝 documentation','priority:medium','phase:hardening','⚡ parallelizable')

# ============================================================
# POST-MVP
# ============================================================
$body = @'
## Description
MVP+1. Daily reconciliation between BC posted receipts and Cosmos audit trail. Flags drift.

## Acceptance Criteria
- [ ] Scheduled ACA Job
- [ ] Drift report email
- [ ] Auto-fix proposals (HITL gated)

## Agent
Bishop (AI Agents)
'@
$ids['post-a7'] = New-Issue `
  -Title "🤖 [Post-MVP] A7 Reconciliation agent — daily BC vs Cosmos" `
  -Body $body `
  -Labels @('squad:bishop','🤖 ai-agents','priority:medium','phase:post-mvp','⚡ parallelizable')

$body = @'
## Description
MVP+2. Learns per-supplier behaviour (typical discrepancies, lateness, signature reliability) and feeds A2 triage policy.

## Acceptance Criteria
- [ ] Reputation model + storage
- [ ] Feedback loop into feature flags
- [ ] Explainability per decision

## Agent
Bishop (AI Agents)
'@
$ids['post-a8'] = New-Issue `
  -Title "🤖 [Post-MVP] A8 Learning agent — supplier reputation + pattern analysis" `
  -Body $body `
  -Labels @('squad:bishop','🤖 ai-agents','priority:low','phase:post-mvp','⚡ parallelizable')

# ============================================================
# Persist mapping
# ============================================================
$mapPath = Join-Path $PSScriptRoot '..' 'decisions' 'inbox' 'hicks-issue-map.json'
$ids | ConvertTo-Json -Depth 4 | Out-File -FilePath $mapPath -Encoding utf8
Write-Host "==> Issue map saved to $mapPath" -ForegroundColor Green
