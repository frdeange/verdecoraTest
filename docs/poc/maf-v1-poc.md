# MAF v1.0 PoC — Results & Recommendations

**Author:** Ash (MAF Specialist)
**Date:** 2026-05-04
**Issue:** #1 — MAF v1.0 PoC in Azure Container Apps
**Status:** Complete

---

## 1. What Was Tested

This PoC validates the Microsoft Agent Framework v1.0 GA SDK for our albarán processing pipeline, specifically:

| Pattern | Builder | Agents | Purpose |
|---------|---------|--------|---------|
| Sequential pipeline | `SequentialBuilder` | StubExtractor | Linear agent chain (extraction step) |
| Conditional handoff | `HandoffBuilder` | StubValidator → StubInventory | Routing based on validation outcome |
| HITL escape hatch | HandoffBuilder `"user"` target | StubValidator | Pause workflow on discrepancy |
| Observability | OpenTelemetry `ConsoleSpanExporter` | All | Trace extraction + validation spans |
| Dry-run mode | Direct tool invocation | None (no LLM) | Test tools without cloud deps |

### Architecture Validated

```
Input (albarán text)
  │
  ▼
┌─────────────────────────────────────────┐
│  Stage 1: SequentialBuilder             │
│  ┌──────────────┐                       │
│  │ StubExtractor │ → extracted JSON     │
│  └──────────────┘                       │
└─────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────┐
│  Stage 2: HandoffBuilder                │
│  ┌───────────────┐   coincide   ┌──────────────┐
│  │ StubValidator  │────────────→│ StubInventory │ → receipt ID
│  └───────┬───────┘              └──────────────┘
│          │ discrepancia
│          ▼
│    HandOff to "user" (HITL)
└─────────────────────────────────────────┘
```

---

## 2. What Works

### ✅ Confirmed Patterns

1. **`SequentialBuilder` API** — `SequentialBuilder(participants=[...]).build()` followed by `workflow.run(input, stream=True)` with async iteration. Clean and intuitive.

2. **`HandoffBuilder` API** — `HandoffBuilder(name=..., participants=[...]).with_start_agent(agent).build()` correctly wires conditional routing. Agents use `handoffs=[...]` to declare targets.

3. **`@tool` decorator** — `@tool(approval_mode="never_require")` with `Annotated` parameters provides clean tool definitions. The framework handles JSON serialization/deserialization.

4. **HITL via `"user"` handoff** — Setting `handoffs=["StubInventory", "user"]` on StubValidator enables the agent to route to a human when discrepancies are found. This is the AutoGen swarm pattern ported to MAF.

5. **`require_per_service_call_history_persistence=True`** — Required on all handoff participants. Ensures conversation history flows through the handoff chain.

6. **OpenTelemetry integration** — `TracerProvider` + `ConsoleSpanExporter` works out of the box. Custom spans via `tracer.start_as_current_span()` provide clean trace hierarchy.

7. **Agent as factory pattern** — Creating agents via factory functions (`create_extractor(client)`) allows easy swapping of the chat client (Foundry / OpenAI / mock).

### ✅ SDK Installation

```bash
pip install agent-framework>=1.0.0
```

- Package name: `agent-framework` (not `microsoft-agent-framework`)
- Import path: `from agent_framework import Agent, tool`
- Orchestrations: `from agent_framework.orchestrations import SequentialBuilder, HandoffBuilder`
- Python 3.10+ required

---

## 3. What Doesn't Work / Caveats

### ⚠️ Known Limitations

1. **No conditional branching in SequentialBuilder** — It's strictly linear. For our full pipeline (where extraction may fail), we need HandoffBuilder or WorkflowBuilder.

2. **HandoffBuilder routing is LLM-dependent** — The agent's `instructions` determine handoff decisions. No explicit routing table. This means:
   - Routing correctness depends on prompt quality
   - Must test with real LLM to validate routing decisions
   - Consider WorkflowBuilder for deterministic business rules

3. **`_MockChatClient` limitation** — The dry-run mode bypasses the Agent framework entirely (calls tools directly). A proper mock would need to implement the chat client protocol. This is fine for tool validation but doesn't test orchestration wiring.

4. **Streaming API** — `async for event in workflow.run(..., stream=True)` works, but `event.type` values and `event.data` structure need live testing to confirm exact field names.

5. **No `WorkflowBuilder` in this PoC** — Per research, `WorkflowBuilder` with `Case`/`Default` conditional edges is the best fit for our deterministic process. Sprint 1 should implement this.

---

## 4. Code Patterns Confirmed

### Pattern 1: Agent Factory

```python
def create_extractor(client) -> Agent:
    return Agent(
        client=client,
        name="ExtractionAgent",
        instructions="...",
        tools=[extract_document],
    )
```

**Recommendation:** Use this pattern for all agents. Keeps client injection separate from agent logic.

### Pattern 2: Two-Stage Orchestration

```python
# Stage 1: Sequential extraction
extracted = await run_extraction_pipeline(client, input_text, tracer)

# Stage 2: Handoff validation → posting
result = await run_validation_handoff(client, extracted, tracer)
```

**Recommendation:** Composing SequentialBuilder + HandoffBuilder gives us the flexibility to add stages without restructuring.

### Pattern 3: Mock Tools for Testing

```python
@tool(approval_mode="never_require")
def extract_document(document_url: Annotated[str, "..."]) -> str:
    return json.dumps({...})  # Mock data
```

**Recommendation:** Keep mock tools as the test harness. In production, replace with `MCPStreamableHTTPTool` pointing to real MCP servers.

### Pattern 4: Telemetry Wrapping

```python
with tracer.start_as_current_span("extraction_pipeline") as span:
    span.set_attribute("input.text", input_text)
    result = await run_pipeline(...)
    span.set_attribute("extraction.complete", True)
```

**Recommendation:** Wrap each stage in a span. Use `span.add_event()` for agent handoff events.

---

## 5. Recommendations for Sprint 1

### 5.1 Architecture

| Decision | Recommendation | Rationale |
|----------|---------------|-----------|
| Primary orchestration | **WorkflowBuilder** with `Case`/`Default` | Deterministic routing for business rules; supports checkpointing |
| HITL integration | HandoffBuilder `"user"` + Cosmos checkpoint | Pause → persist → resume after human review |
| Cross-container | **A2A protocol** (`agent-framework-a2a`) | Each agent in its own ACA container |
| Telemetry | `configure_azure_monitor()` + `enable_instrumentation()` | Application Insights for production |

### 5.2 Agent Design

1. **Replace mock tools with `MCPStreamableHTTPTool`** pointing to:
   - Document Intelligence MCP server
   - Blob Storage MCP server
   - Business Central MCP server (via BC native MCP)
   - Cosmos DB MCP server

2. **Add `approval_mode="always_require"` for write operations** (inventory posting, BC writes).

3. **System prompts must include explicit handoff criteria** — the LLM uses these to decide routing.

### 5.3 Testing Strategy

1. **Unit tests:** Mock the chat client, verify tool calls and handoff decisions.
2. **Integration tests:** Use `OpenAIChatCompletionClient` with a real model to test prompt effectiveness.
3. **E2E tests:** Deploy to ACA with A2A, test full albarán flow.

### 5.4 Dependencies to Lock

```txt
agent-framework>=1.0.0
agent-framework-a2a>=1.0.0          # For cross-container A2A
agent-framework-azure-cosmos>=1.0.0  # For CosmosCheckpointStorage
azure-identity>=1.17.0
azure-monitor-opentelemetry>=1.6.0
opentelemetry-sdk>=1.25.0
```

---

## 6. Files Created

| File | Purpose |
|------|---------|
| `src/poc/maf_poc/__init__.py` | Package init |
| `src/poc/maf_poc/stub_agents.py` | 3 stub agents with mock tools |
| `src/poc/maf_poc/orchestrator.py` | SequentialBuilder + HandoffBuilder orchestration |
| `src/poc/maf_poc/run_poc.py` | CLI entry point with dry-run support |
| `src/poc/maf_poc/requirements-poc.txt` | Minimal dependencies |
| `docs/poc/maf-v1-poc.md` | This document |

---

## 7. How to Run

```bash
# Install dependencies
pip install -r src/poc/maf_poc/requirements-poc.txt

# Dry-run (no LLM needed)
python -m src.poc.maf_poc.run_poc

# With Azure AI Foundry
export AZURE_AI_PROJECT_ENDPOINT="https://your-project.services.ai.azure.com"
export AZURE_AI_MODEL="gpt-4o"
python -m src.poc.maf_poc.run_poc

# With OpenAI
export OPENAI_API_KEY="sk-..."
python -m src.poc.maf_poc.run_poc

# Custom albarán input
python -m src.poc.maf_poc.run_poc --albaran "Albarán ALB-2026-00200 from ..."
```
