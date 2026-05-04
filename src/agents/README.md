# AI Agents

MAF-based agent implementations for the Verdecora albarán flow.

## Core agents
- `a2-triage` classifies OCR text and decides whether to extract, reject, or send to manual review.
- `a1-extractor` converts Document Intelligence output into `AlbaranExtraction`.
- `a3-coherence` validates the extracted payload against business rules and Business Central data.
- `a6-communication` prepares Spanish HITL notification summaries and escalation handoffs.

## Key modules
- `factory.py` centralises FoundryChatClient creation, model selection, and MCP tool binding.
- `pipeline.py` builds the sequential MAF workflow and supports config-driven stage skipping.
- `prompts/` stores the system prompts used by each agent.
- `_maf_compat.py` returns placeholder specs when `agent-framework` is unavailable so imports remain safe in local dev.

## Configuration
Use `src.config.agents.get_agents_config()` to load defaults from environment variables:
- `AZURE_AI_PROJECT_ENDPOINT`
- `DOCUMENT_INTELLIGENCE_ENDPOINT`
- `GPT5_DEPLOYMENT`
- `GPT5_MINI_DEPLOYMENT`
- `TRIAGE_MANUAL_REVIEW_THRESHOLD`
- `LOW_VALUE_COHERENCE_THRESHOLD`
- `SKIP_TRIAGE_SUPPLIERS`

All Azure access should rely on `DefaultAzureCredential` / managed identity only.

## FoundryChatClient pattern
```python
from src.agents import build_pipeline
from src.config import get_agents_config

config = get_agents_config()
credential = config.create_credential()
pipeline = build_pipeline(
    config=config,
    project_endpoint=config.endpoints.azure_ai_project_endpoint,
    credential=credential,
    tool_registry={
        "extractor": [content_understanding_mcp],
        "coherence": [bc_mcp],
    },
)
```

## Multi-model setup
The pipeline creates one `FoundryChatClient` per model:
- `gpt-5` for `a1-extractor`
- `gpt-5-mini` for `a2-triage`, `a3-coherence`, `a4-validator`, `a5-inventory`, and `a6-communication`

You can also pass pre-built `gpt5_client` and `gpt5_mini_client` instances into `build_pipeline()` or `AlbaranPipeline()`.
