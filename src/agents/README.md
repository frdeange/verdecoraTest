# AI Agents

MAF-based agent implementations for the Verdecora albarán flow.

## Core agents
- `a2-triage` classifies OCR text and decides whether to extract, reject, or send to manual review.
- `a1-extractor` converts Document Intelligence output into `AlbaranExtraction`.
- `a3-coherence` validates the extracted payload against business rules and Business Central data.
- `a6-communication` prepares Spanish HITL notification summaries and escalation handoffs.

## Key modules
- `factory.py` centralises model selection, prompt injection, and MCP tool binding.
- `pipeline.py` builds the sequential MAF workflow and supports config-driven stage skipping.
- `prompts/` stores the system prompts used by each agent.
- `_maf_compat.py` returns placeholder specs when `agent-framework` is unavailable so imports remain safe in local dev.

## Configuration
Use `src.config.agents.get_agents_config()` to load defaults from environment variables:
- `AZURE_OPENAI_ENDPOINT`
- `DOCUMENT_INTELLIGENCE_ENDPOINT`
- `GPT5_DEPLOYMENT`
- `GPT5_MINI_DEPLOYMENT`
- `TRIAGE_MANUAL_REVIEW_THRESHOLD`
- `LOW_VALUE_COHERENCE_THRESHOLD`
- `SKIP_TRIAGE_SUPPLIERS`

All Azure access should rely on `DefaultAzureCredential` / managed identity only.

## Example
```python
from src.agents import build_pipeline
from src.config import get_agents_config

config = get_agents_config()
pipeline = build_pipeline(client=my_maf_client, config=config, tool_registry={
    "extractor": [content_understanding_mcp],
    "coherence": [bc_mcp],
})
```
