# Bishop — History

## Project Context
- **Project:** Sistema Inteligente de Gestión de Albaranes
- **User:** Kiko de Angel
- **Role:** AI Agent Developer
- **Stack:** Python, Microsoft Agent Framework v1.0+, Azure AI Document Intelligence v4.0, Azure OpenAI
- **PRD:** prerequisites/pliego-tecnico-albaranes.html

## Learnings

### 2026-05-03 — LLM model evaluation and OCR strategy
- Reviewed the PRD assumptions around GPT-4o / GPT-4.1 and the proposed unconditional double-pass OCR pipeline.
- Evaluated current Azure OpenAI / Foundry options, including GPT-5 family, GPT-4.1, GPT-4o, o-series, and Claude availability in Foundry.
- Recommended GPT-5 family as the new production baseline, with `gpt-5-mini` for Agent 1 and Agent 3, and `gpt-5.5` for Agent 2.
- Recommended keeping Azure AI Document Intelligence as the OCR foundation, but changing the design from unconditional double-pass to selective hybrid escalation.
- Wrote full findings to `prerequisites/analysis/bishop-llm-evaluation.md` and decision summary to `.squad/decisions/inbox/bishop-llm-models.md`.

### 2026-05-05 — MAF v1.2.2 migration behavior
- Upgrading to MAF v1.2.2 requires using `agent_framework.Agent` directly; `ChatAgent` is no longer exported from the top-level package.
- Structured outputs now belong in `default_options={"response_format": Model}` instead of passing `response_format=` to the agent constructor.
- Sequential workflow output handlers must normalize `AgentResponse` values by reading `.text` first and falling back to `.messages[-1].content` when needed.
- `SequentialBuilder` should be imported from `agent_framework.orchestrations` for v1.2.2-compatible code paths.

### 2026-05-07 — Real OCR agent validation on Azure
- Validated a live A1/A2 path with Azure Document Intelligence OCR plus Azure OpenAI against `prerequisites/PRUEBA.pdf`, using `DefaultAzureCredential` and the `openai.AzureOpenAI` client.
- The checked-in `PRUEBA.pdf` is a mixed-document batch; stable extractor/triage validation comes from the first page, which is a single Herstera albarán with supplier, date, quantities, and prices.
- GPT-5 extractor calls can exhaust smaller `max_completion_tokens` budgets entirely on reasoning; a budget around `8000` was needed to get visible structured JSON output for the real OCR extraction prompt.
- Added `tests/integration/test_agent_real.py` with a live-service gate (`RUN_AGENT_REAL_INTEGRATION=1`) so the repo keeps an executable real Azure OCR + agent smoke test without forcing network calls in default pytest runs.
