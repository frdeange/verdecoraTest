# Current Focus

## What We're Doing
**Phase: Analysis COMPLETE → Issue Creation in progress → Sprint 0 next**

Kiko went to sleep at 23:46 on 2026-05-03. Autopilot mode active.

## What Was Accomplished Today (2026-05-03)

### Team
- 13 specialists hired (Alien universe) + Scribe + Ralph
- Brett added mid-session as Private Network & CI/CD Specialist

### Architecture (ADR v3 — APPROVED by Kiko)
- **6 AI agents MVP** (was 3 in PRD): Extractor, Triage, Coherence, Validator, Inventory, Communication
- **2 deferred**: Reconciliation (MVP+1), Learning (MVP+2)
- **All agents in ACA** with MAF SDK in-process (HandOff pattern)
- **No Durable Functions** — ACA + Service Bus for everything
- **No A2A** — agents in-process, future migration to hosted-agents if needed
- **Foundry = model endpoints only** (Azure OpenAI GPT-5.1 + GPT-5-mini)
- **ACS Email + web form** for HITL (not Teams, not WorkIQ, not Power Automate)
- **Service Bus scheduled messages** for HITL timers (24h/48h/72h)
- **Private VNet** in Sweden Central with self-hosted GitHub runners in ACA
- **Triage uses GPT-5-mini + structured output** (not rule-based)

### Key Decisions (25 total in ADR §11)
- D-R-001 through D-R-025 documented and approved

### Research Completed (8 analysis documents)
- prerequisites/analysis/ripley-requirements-analysis.md
- prerequisites/analysis/ripley-agentic-redesign.md
- prerequisites/analysis/ash-maf-research.md
- prerequisites/analysis/ash-maf-multiagent-patterns.md
- prerequisites/analysis/newt-mcp-analysis.md
- prerequisites/analysis/newt-workiq-hitl-analysis.md
- prerequisites/analysis/newt-acs-email-hitl.md
- prerequisites/analysis/bishop-llm-evaluation.md
- prerequisites/analysis/burke-bc-analysis.md
- prerequisites/analysis/call-foundry-research.md
- prerequisites/analysis/brett-private-networking.md

## In Progress Right Now
- ⚙️ Hicks creating ~50 GitHub issues for full project backlog

## Assumptions Made During Autopilot (Kiko was asleep)
- Hicks couldn't create GitHub issues due to pull-only permissions on the EMU account. He created a PowerShell script instead: `.squad/scripts/create-backlog.ps1` with all 50 issues + labels. Kiko needs to run it manually.
- No other assumptions were needed — all work was mechanical (logging, committing).

## Next Steps (when Kiko wakes up)
1. Review the GitHub issues Hicks created
2. Approve Sprint 0 scope and start execution
3. Agents begin Sprint 0 tasks (PoCs, Bicep foundation, CI/CD)

## Open Items Requiring Kiko's Input
- O-7: Reject path — does the supplier get notified?
- O-6: Approver routing per tienda (responsable_principal, backup, escalacion_a)
- GitHub labels need admin permissions to create (Hicks was blocked earlier)
