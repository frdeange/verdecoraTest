# Bishop — History

## Project Context
- **Project:** Sistema Inteligente de Gestión de Albaranes
- **User:** Kiko de Angel
- **Role:** AI Agent Developer
- **Stack:** Python, Microsoft Agent Framework v1.0+, Azure AI Document Intelligence v4.0, Azure OpenAI
- **PRD:** prerequisites/pliego-tecnico-albaranes.html

## Learnings

### 2026-05-05 — Upload Web store detection heuristic spike
- Implemented `src/upload_web/services/store_detector.py` with a hardcoded Verdecora store catalog and deterministic matching heuristic for Upload Web preflight.
- Prioritized exact postal code matches, then fuzzy city + street scoring with accent/punctuation normalization and proposal-aligned confidence bands (`>=0.85` auto-select, `0.5-0.85` suggest, `<0.5` no suggestion).
- Left unresolved public-store records (for example Valencia Av. Puerto, Dénia, Sant Quirze, Alicante) without a trusted postal code so the spike does not over-assert on weak catalog data.
- Added unit coverage in `tests/unit/test_store_detector.py` for postal match, city-only suggestion, no-match, accent handling, and partial-address matching.

### 2026-05-03 — LLM model evaluation and OCR strategy
- Reviewed the PRD assumptions around GPT-4o / GPT-4.1 and the proposed unconditional double-pass OCR pipeline.
- Evaluated current Azure OpenAI / Foundry options, including GPT-5 family, GPT-4.1, GPT-4o, o-series, and Claude availability in Foundry.
- Recommended GPT-5 family as the new production baseline, with `gpt-5-mini` for Agent 1 and Agent 3, and `gpt-5.5` for Agent 2.
- Recommended keeping Azure AI Document Intelligence as the OCR foundation, but changing the design from unconditional double-pass to selective hybrid escalation.
- Wrote full findings to `prerequisites/analysis/bishop-llm-evaluation.md` and decision summary to `.squad/decisions/inbox/bishop-llm-models.md`.

### 2026-05-05 — MAF v1.2.2 upgrade execution and breaking change adaptation
- Received upgrade requirement from Ash (MAF v1.2.2 impact analysis).
- Executed upgrade: Updated `pyproject.toml` to pin `agent-framework>=1.2.2,<2.0`.
- Adapted breaking changes:
  1. **AgentResponse standardization** (#5301): Modified `_run_workflow()` handlers in pipeline.py, reconciler.py, analyzer.py to normalize `.text` / `.messages[-1].content` output.
  2. **ChatAgent deprecation:** Standardized all agent code on `agent_framework.Agent` direct usage.
  3. **Structured output configuration:** Updated to `default_options={"response_format": Model}` pattern.
  4. **CosmosCheckpointStorage prep:** Ready for `allowed_checkpoint_types` support (breaking change #5200).
- Test validation: 171 tests passed, 7 skipped (non-blocking).
- PR #86 created with commit 61151de.
- Sprint 1 WorkflowBuilder development now unblocked with stable MAF baseline.

