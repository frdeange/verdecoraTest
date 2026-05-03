# Work Routing

How to decide who handles what.

## Routing Table

| Work Type | Route To | Examples |
|-----------|----------|----------|
| Architecture & requirements | Ripley | Flow design, architecture decisions, component boundaries, code review |
| AI agent development | Bishop | Agent 1/2/3 implementation, LLM config, Agent Framework code |
| DevOps & CI/CD | Hicks | Issues, branches, pipelines, PR workflow, GitHub Actions |
| Azure infrastructure | Dallas | Bicep IaC, Container Apps, networking, resource provisioning |
| Backend services | Parker | Webhooks, Change Feed processor, Teams HITL bot, Container Apps services |
| Security & identity | Lambert | Entra ID, Managed Identities, Key Vault, Private Endpoints, RBAC |
| Testing & QA | Vasquez | Test plans, E2E tests, OCR validation, load tests, quality gates |
| Business Central | Burke | BC entities, Purchase Orders, inventory, AL customization, BC config |
| Documentation | Hudson | Technical docs, runbooks, operation guides, user manuals |
| Agent Framework research | Ash | MAF v1.0 capabilities, patterns, SDK exploration, best practices |
| MCP strategy | Newt | MCP analysis, available MCPs, integration patterns, MCP server design |
| Azure AI Foundry | Call | Foundry Agent Service, persistent agents, model deployment, Foundry config |
| Private networking & CI/CD | Brett | VNet, Private Endpoints, self-hosted runners, DNS, NAT Gateway, bootstrap |
| Code review | Ripley | Review PRs, architectural quality, approve/reject |
| Scope & priorities | Ripley | What to build next, trade-offs, decisions |
| Session logging | Scribe | Automatic — never needs routing |
| Work monitoring | Ralph | Backlog, issue tracking, pipeline status |

## Issue Routing

| Label | Action | Who |
|-------|--------|-----|
| `squad` | Triage: analyze issue, assign `squad:{member}` label | Ripley (Lead) |
| `squad:ripley` | Architecture and design tasks | Ripley |
| `squad:bishop` | AI agent implementation | Bishop |
| `squad:hicks` | DevOps, CI/CD, pipeline tasks | Hicks |
| `squad:dallas` | Azure infrastructure, Bicep | Dallas |
| `squad:parker` | Backend services, webhooks | Parker |
| `squad:lambert` | Security configuration | Lambert |
| `squad:vasquez` | Testing tasks | Vasquez |
| `squad:burke` | Business Central integration | Burke |
| `squad:hudson` | Documentation tasks | Hudson |
| `squad:ash` | MAF research tasks | Ash |
| `squad:newt` | MCP analysis tasks | Newt |
| `squad:call` | Foundry configuration tasks | Call |
| `squad:brett` | Private networking tasks | Brett |

### How Issue Assignment Works

1. When a GitHub issue gets the `squad` label, **Ripley** triages it — analyzing content, assigning the right `squad:{member}` label, and commenting with triage notes.
2. When a `squad:{member}` label is applied, that member picks up the issue in their next session.
3. Members can reassign by removing their label and adding another member's label.
4. The `squad` label is the "inbox" — untriaged issues waiting for Ripley's review.

## Rules

1. **No work without an Issue** — every task must have a GitHub Issue before work starts.
2. **Strict DevOps cycle** — Issue → Branch → Dev → Test → Commit → Push → PR → Review → Merge → Close.
3. **Eager by default** — spawn all agents who could usefully start work, including anticipatory downstream work.
4. **Scribe always runs** after substantial work, always as `mode: "background"`. Never blocks.
5. **Quick facts → coordinator answers directly.** Don't spawn an agent for simple factual questions.
6. **When two agents could handle it**, pick the one whose domain is the primary concern.
7. **"Team, ..." → fan-out.** Spawn all relevant agents in parallel as `mode: "background"`.
8. **Anticipate downstream work.** If a feature is being built, spawn the tester to write test cases simultaneously.
9. **Hicks enforces DevOps.** Work without proper issue/branch/PR workflow is rejected.
