# Session Log: 2026-05-03T2230 — Wave 2 Architecture

**Date:** 2026-05-03  
**Time:** 22:30 UTC  
**Agents:** Ripley, Newt, Brett  
**Outcome:** Architecture v2 locked; 15/18 decisions ratified; 3 provisional; IaC-ready

## Key Outputs

- **docs/architecture/architecture-decision-record.md** — Definitive architecture (components, flows, state machine, LLM strategy, MCP scope, partition key, security baseline)
- **prerequisites/analysis/ripley-requirements-analysis.md** — Detailed design re-evaluation
- **prerequisites/analysis/newt-workiq-hitl-analysis.md** — Email HITL feasibility; WorkIQ role scoped
- **prerequisites/analysis/brett-private-networking.md** — Private VNet + ACA Jobs bootstrap; private DNS baseline

## Decisions Ratified (Locked)

✅ LLM versions pinned (D-R-001)  
✅ State machine 13+1 (D-R-005)  
✅ Idempotency two-stage (D-R-006)  
✅ Cosmos partition key `tienda_id_yyyymm` (D-R-007)  
✅ Sweden Central region (D-R-008)  
✅ 2% global tolerance (D-R-009)  
✅ Albarán canonical ID (D-R-010)  
✅ Security coherence validation (D-R-011)  
✅ Private VNet + self-hosted runners (D-R-012)  
✅ MCP scope finalized (D-R-013)  
✅ No DELETE on MCP (D-R-014)  
✅ Model version pinning (D-R-015)  
✅ 6-year immutable retention (D-R-016)  
✅ No cost ceiling; budget alerts (D-R-017)

## Provisional (Tracked in ADR Open Items)

⏳ OCR strategy lock pending Sprint 0 benchmark (D-R-002)  
⏳ WorkIQ implementation choice pending decision (D-R-004)  
⏳ BC custom AL validation pending Sprint 0 (D-R-018)

## Open Flags for Kiko Review (Brett)

- GitHub public egress dependency acceptable?
- Docker builds: second runner pool or ACR Tasks?
- Service Bus Premium tier approved?

## Next Steps

1. Kiko review + close Brett's open flags
2. Dallas: Bicep IaC against component table
3. Hicks: CI/CD self-hosted runner bootstrap
4. Sprint 0: Ash OCR benchmark, Newt WorkIQ impl. choice, Burke BC validation
