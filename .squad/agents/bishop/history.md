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
