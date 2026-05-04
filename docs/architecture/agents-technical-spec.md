# Core agents technical specification

## Scope

This document describes the **implemented** core agents in `src/agents/`:

- **A1 Extractor**
- **A2 Triage**
- **A3 Coherence**

> The broader ADR describes a six-agent target architecture. The current codebase implements the first three agents only, using the Microsoft Agent Framework (MAF) **in-process** pattern inside one Python application.

## Architecture overview

### Runtime pattern

The code uses a small compatibility layer in `src/agents/_maf_compat.py` to build agents and workflows without hard-coupling the rest of the code to one MAF constructor shape.

```python
return create_structured_agent(
    client=client,
    name="a1-extractor",
    model=resolved_config.models.extractor_model,
    instructions=_build_extractor_instructions(tool_names),
    structured_output=AlbaranExtraction,
    tools=resolved_tools,
    handoffs=["a3-coherence"],
)
```

At runtime:

1. `factory.py` creates the three agents.
2. `pipeline.py` decides which stages to run.
3. Each stage is executed as a **single-step `SequentialBuilder` workflow**.
4. Outputs are validated back into Pydantic models.

### Important implementation note

`AlbaranPipeline.build_workflow()` can assemble a combined sequential workflow for inspection/testing, but `AlbaranPipeline.run()` currently executes **three separate single-step workflows** (`triage`, `extractor`, `coherence`) with explicit Python control flow between them.

## End-to-end data flow

```mermaid
flowchart TD
    A[PipelineDocumentInput] --> B{Skip triage?}
    B -- yes --> E[Extractor]
    B -- no --> C[Triage]
    C --> D{routing_decision == "extract"?}
    D -- no --> Z[Return early\ntriage only]
    D -- yes --> E[Extractor]
    E --> F{Skip coherence?}
    F -- yes --> Y[Return extraction result]
    F -- no --> G[Coherence]
    G --> H[PipelineRunResult]
```

### Stage inputs used by `pipeline.py`

| Stage | Payload sent to workflow |
|---|---|
| Triage | `raw_text` if present, otherwise `document_reference` |
| Extractor | `ocr_payload` if present, otherwise `raw_text`, otherwise `document_reference` |
| Coherence | `extraction_result.model_dump(mode="json")` if extraction succeeded, otherwise the extractor payload fallback |

## Agent factory and orchestration modules

| Module | Responsibility |
|---|---|
| `src/agents/triage_agent.py` | Builds A2 with `TriageResult` structured output |
| `src/agents/extractor_agent.py` | Builds A1 with `AlbaranExtraction` structured output |
| `src/agents/coherence_agent.py` | Builds A3 with `CoherenceCheckResult` structured output |
| `src/agents/factory.py` | Resolves config and tool registry, returns all three agents |
| `src/agents/pipeline.py` | Applies skip logic and runs the stage sequence |
| `src/agents/_maf_compat.py` | MAF compatibility wrapper + graceful fallback when `agent-framework` is missing |

## Agent specifications

## A2 Triage agent

### Purpose

Classify raw OCR text and decide whether the document should continue through the extraction pipeline.

### Primary responsibility

- Identify document type: `albaran`, `factura`, `packing_list`, or `unknown`
- Detect language
- Capture supplier hint if possible
- Produce a routing decision

### Model selection

- **Configured model:** `config.models.triage_model`
- **Default deployment:** `gpt-5-mini`

Why this model split exists in code:

- Triage works on **text classification and routing**, not heavy field extraction.
- `AgentModelSettings` intentionally assigns the cheaper/faster mini deployment to triage.

### Input/output contract

**Input:** free-form string payload from OCR text (`raw_text`) or a fallback document reference.

**Structured output:** `src.models.albaran.TriageResult`

```python
class TriageResult(BaseModel):
    document_type: DocumentType
    language: str = "es"
    supplier_id: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    routing_decision: str
    reasoning: str
```

### Prompt strategy

- Prompt lives in `prompts/triage_prompt.py`
- Runtime injects `TriageResult.model_json_schema()` into the system prompt
- Prompt is intentionally conservative: if unsure, prefer `manual_review`
- Prompt includes multilingual keyword hints for Spanish, Italian, and German delivery documents

### MCP tools

- `create_triage_agent()` accepts optional tools
- No default MCP tool names are appended to the prompt
- In the current codebase, triage is tool-ready but not tool-opinionated

### Handoffs

Declared handoffs: `a1-extractor`, `user`

These handoff names are embedded in the agent definition, but the current `run()` implementation does **not** use `HandoffBuilder`; routing is enforced in Python by checking `routing_decision`.

### Error handling behavior

- If the workflow backend is unavailable, `run()` raises a `RuntimeError` via `ensure_workflow_available()`
- If streamed or returned output cannot be validated into `TriageResult`, the stage returns `None`
- Any `routing_decision` other than `"extract"` stops the pipeline early

## A1 Extractor agent

### Purpose

Convert OCR-derived content for an albarán/factura into the project’s canonical extraction model.

### Primary responsibility

- Populate `AlbaranHeader`
- Extract all `LineItem` rows
- Estimate extraction confidence
- Produce extraction warnings and source page references

### Model selection

- **Configured model:** `config.models.extractor_model`
- **Default deployment:** `gpt-5`

Why this model split exists in code:

- Extraction is the most schema-heavy stage and must recover structured data from messy OCR/table content.
- `AgentModelSettings` assigns the full `gpt-5` deployment to extraction by default.

### Input/output contract

**Input:** `ocr_payload`, or fallback `raw_text`, or fallback `document_reference`.

**Structured output:** `src.models.albaran.AlbaranExtraction`

```python
class AlbaranExtraction(BaseModel):
    header: AlbaranHeader
    line_items: list[LineItem]
    raw_text: str | None = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    extraction_warnings: list[str] = Field(default_factory=list)
    source_pages: list[int] = Field(default_factory=list)
```

### Prompt strategy

- Prompt lives in `prompts/extractor_prompt.py`
- Runtime injects `AlbaranExtraction.model_json_schema()`
- Prompt explicitly asks for:
  - complete header extraction
  - complete line-item extraction
  - confidence scoring
  - warning generation
  - multi-page aggregation
  - barcode/EAN preservation

The builder also appends a tool hint:

```python
tool_hint = "\nAvailable MCP tools: " + ", ".join(tool_names)
```

### MCP tools

Default tool names documented in code:

- `content_understanding.analyze_document`
- `content_understanding.extract_tables`

Actual tool objects come from `tool_registry["extractor"]`.

### Handoffs

Declared handoff: `a3-coherence`

As with triage, this is future-friendly metadata in the current implementation; stage progression is handled directly in Python.

### Error handling behavior

- Invalid structured output is coerced to `None`
- Pipeline still proceeds to coherence with a fallback payload if extraction returns `None`
- No extractor-specific retry policy is implemented in this module

## A3 Coherence agent

### Purpose

Validate the extraction result against business rules and, when tools are available, Business Central lookup results.

### Primary responsibility

- Check header plausibility
- Check line-item quantities/prices/totals
- Indicate whether a BC match was found
- Propose corrections when issues are detected

### Model selection

- **Configured model:** `config.models.coherence_model`
- **Default deployment:** `gpt-5-mini`

Why this model split exists in code:

- Coherence is primarily a text-and-logic validation stage over already structured JSON.
- The config mirrors triage by using the lighter model by default.

### Input/output contract

**Input:** serialized `AlbaranExtraction` JSON when extraction succeeds; otherwise the extractor fallback payload.

**Structured output:** `src.models.albaran.CoherenceCheckResult`

```python
class CoherenceCheckResult(BaseModel):
    is_coherent: bool
    overall_confidence: float = Field(ge=0.0, le=1.0)
    header_issues: list[str] = Field(default_factory=list)
    line_item_issues: list[str] = Field(default_factory=list)
    bc_match_found: bool = False
    matched_po_number: str | None = None
    suggested_corrections: dict[str, str] = Field(default_factory=dict)
```

### Prompt strategy

- Prompt lives in `prompts/coherence_prompt.py`
- Runtime injects `CoherenceCheckResult.model_json_schema()`
- Prompt asks the model to apply:
  - header checks
  - line-item math/coherence checks
  - BC cross-reference checks when available
  - 2% total-tolerance validation

### MCP tools

Default tool names documented in code:

- `bc.search_vendors`
- `bc.search_purchase_orders`
- `bc.search_items`

Actual tool objects come from `tool_registry["coherence"]`.

### Error handling behavior

- Invalid structured output becomes `None`
- If `PipelineDocumentInput.total_amount` is below the configured threshold, the entire coherence stage is skipped
- The stage does not throw on validation issues; it returns a `CoherenceCheckResult` describing them

## Configuration

## `AgentsConfig`

`src/config/agents.py` groups agent settings into endpoints, model names, thresholds, and triage-skip suppliers.

| Environment variable | Default | Used by |
|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | `https://verdecora-openai-dev.openai.azure.com/` | Client construction outside agent factories |
| `DOCUMENT_INTELLIGENCE_ENDPOINT` | `https://verdecora-docintell-dev.cognitiveservices.azure.com/` | OCR / document client construction outside agent factories |
| `AZURE_OPENAI_API_VERSION` | `2024-10-21` | Client construction outside agent factories |
| `GPT5_DEPLOYMENT` | `gpt-5` | Extractor model selection |
| `GPT5_MINI_DEPLOYMENT` | `gpt-5-mini` | Triage + coherence model selection |
| `TRIAGE_MANUAL_REVIEW_THRESHOLD` | `0.65` | Present in config, **not currently consumed** by pipeline/agent code |
| `LOW_VALUE_COHERENCE_THRESHOLD` | `250.0` | Skip coherence when `total_amount` is below this value |
| `SKIP_TRIAGE_SUPPLIERS` | empty | Skip triage when `supplier_id` or `supplier_hint` matches one of these tokens |

### Credential creation

`AgentsConfig.create_credential()` returns:

```python
DefaultAzureCredential(exclude_interactive_browser_credential=True)
```

This keeps the agent runtime aligned with managed identity / workload identity patterns.

## Pipeline control logic

### Triage skip

Triage is skipped when either `supplier_id` or `supplier_hint` matches `skip_triage_suppliers` case-insensitively.

### Coherence skip

Coherence is skipped when `total_amount < low_value_coherence_threshold`.

### Result shape

The pipeline returns a `PipelineRunResult`:

```python
class PipelineRunResult(BaseModel):
    triage: TriageResult | None = None
    extraction: AlbaranExtraction | None = None
    coherence: CoherenceCheckResult | None = None
    routing_decision: str
    skipped_steps: list[str] = Field(default_factory=list)
```

## MAF compatibility and failure modes

`src/agents/_maf_compat.py` supports three operating modes:

1. **Preferred:** `AgentBuilder` / `SequentialBuilder` available
2. **Fallback:** `Agent` available but builder APIs differ
3. **Unavailable:** return `UnavailableAgentSpec` / `UnavailableWorkflowSpec`

This allows imports and unit tests to work even when `agent-framework` is not installed locally.

### Practical implications

- Agent creation can succeed in "spec only" mode
- Pipeline execution cannot run in that mode
- `coerce_model()` intentionally suppresses `ValidationError`, `TypeError`, and `ValueError`, returning `None` instead of crashing the run

## Deployment notes (ACA + Managed Identity)

## What the code assumes

The core agent code assumes:

- agents run **in-process** inside one Python service
- the caller injects a ready-made MAF chat client
- Azure authentication uses `DefaultAzureCredential` / managed identity
- MCP tools are injected from outside via a registry

## What the repo infrastructure already provisions

The current infrastructure modules provision the Azure dependencies needed by the future ACA-hosted orchestrator:

- **Azure OpenAI** account with `disableLocalAuth: true`
- **Document Intelligence** account with `disableLocalAuth: true`
- **user-assigned managed identity** `agentic-orchestrator`
- RBAC for that identity on:
  - Azure OpenAI (`Cognitive Services OpenAI User`)
  - Document Intelligence (`Cognitive Services User`)
  - Cosmos DB
  - Service Bus
  - Blob Storage
  - Key Vault

## Current gap to be aware of

The repository contains the identity/RBAC foundation and the architectural ADR for ACA deployment, but **this branch does not yet define the actual `agentic-orchestrator` Azure Container App resource**. In other words:

- **deployment target:** ACA
- **identity model:** managed identity
- **implemented infra here:** supporting resources and RBAC
- **not yet present here:** the concrete container app manifest for the three-agent runtime

## Minimal code wiring example

```python
from src.agents import build_pipeline
from src.config import get_agents_config

config = get_agents_config()
pipeline = build_pipeline(
    client=my_maf_client,
    config=config,
    tool_registry={
        "extractor": [content_understanding_mcp],
        "coherence": [bc_mcp],
    },
)
```

## Summary

The implemented A1-A3 design is a pragmatic in-process MAF pipeline:

- **A2 Triage** decides whether to continue
- **A1 Extractor** produces the canonical albarán JSON
- **A3 Coherence** validates the result

The design is already structured for ACA + managed identity deployment, while keeping local development safe through `_maf_compat.py` and Pydantic-based structured outputs.
