# Decision: MAF v1.0 PoC Patterns Validated

**Author:** Ash (MAF Specialist)
**Date:** 2026-05-04
**PR:** #56
**Issue:** #1

## Decision

SequentialBuilder and HandoffBuilder from `agent-framework` v1.0 GA are validated for our albarán processing pipeline. The PoC confirms:

1. **SequentialBuilder** works for linear pipelines but has no conditional branching.
2. **HandoffBuilder** works for conditional routing but depends on LLM prompt quality for decisions.
3. **HITL** via `handoffs=["user"]` correctly pauses workflow for human review.
4. **@tool decorator** with `Annotated` params and `approval_mode` works as documented.
5. **OpenTelemetry** integrates cleanly with custom spans.

## Recommendation for Sprint 1

- Use **WorkflowBuilder** (not SequentialBuilder/HandoffBuilder) for the production pipeline. It supports `Case`/`Default` conditional edges with deterministic routing — better fit for business rules than LLM-driven handoff.
- Keep HandoffBuilder pattern for dynamic edge cases (e.g., complex discrepancy triage).
- Use `CosmosCheckpointStorage` for durable HITL waits (24h reminder, 48h escalation).
- Replace mock tools with `MCPStreamableHTTPTool` pointing to real MCP servers.

## Impact

- Unblocks Sprint 1 agent implementation with confirmed API patterns.
- PRD pseudocode corrections remain valid and are incorporated in the PoC.
