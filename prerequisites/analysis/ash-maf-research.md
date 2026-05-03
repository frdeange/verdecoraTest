# Microsoft Agent Framework v1.0+ — Deep Research Report

**Author:** Ash (MAF Specialist)
**Date:** 2026-05-03
**Status:** Complete
**Sources:** Context7 (microsoft/agent-framework, microsoft/agent-framework-samples, microsoft/autogen), web search, Azure documentation

---

## 1. SDK Current State

### Package & Installation

| Field | Value |
|-------|-------|
| **Package name** | `agent-framework` |
| **Install** | `pip install agent-framework` |
| **Version** | 1.0.0 (GA: April 3, 2026) |
| **Python** | 3.10+ |
| **Import** | `from agent_framework import Agent` |
| **GitHub** | [microsoft/agent-framework](https://github.com/microsoft/agent-framework) |

### Sub-packages (optional installs)

| Package | Purpose |
|---------|---------|
| `agent_framework.foundry` | Azure AI Foundry integration (`FoundryChatClient`) |
| `agent_framework.openai` | OpenAI/GitHub Models (`OpenAIChatClient`, `OpenAIChatCompletionClient`) |
| `agent_framework.orchestrations` | Multi-agent workflows (Sequential, Handoff, GroupChat, Concurrent) |
| `agent_framework.observability` | OpenTelemetry integration |

### Heritage

MAF v1.0 is the **unified successor** to:
- **Semantic Kernel** — kernel, plugins, function-calling patterns
- **AutoGen** — multi-agent orchestration, swarm patterns, handoff protocol

The AutoGen package (`autogen-agentchat`, `autogen-ext`) still exists (v0.7.x) but MAF is the recommended production path. AutoGen concepts (Swarm, HandoffMessage, McpWorkbench) have been ported into `agent_framework`.

---

## 2. Core API Reference

### Key Classes

```python
# Core
from agent_framework import Agent, AgentResponse, Message, tool
from agent_framework import ChatMessage, Role, TextContent, DataContent

# Chat clients
from agent_framework.foundry import FoundryChatClient
from agent_framework.openai import OpenAIChatClient, OpenAIChatCompletionClient

# MCP tools
from agent_framework import MCPStreamableHTTPTool  # HTTP/SSE MCP servers
# Also available: MCPStdioTool for stdio-based MCP servers

# Orchestrations
from agent_framework.orchestrations import (
    SequentialBuilder,
    HandoffBuilder,
    ConcurrentBuilder,
    GroupChatBuilder,
    MagenticBuilder,
)

# Sessions & state
from agent_framework import AgentSession

# Observability
from agent_framework.observability import (
    configure_otel_providers,
    get_tracer,
    create_resource,
    enable_instrumentation,
)

# Hosting
from agent_framework.hosting import AgentFunctionApp  # Azure Functions hosting
```

### Agent Class — Core API

```python
agent = Agent(
    client=FoundryChatClient(...),       # Required: chat client
    name="MyAgent",                       # Agent name
    instructions="System prompt here",    # System instructions
    tools=[tool1, mcp_tool],              # Tools (functions, MCP, etc.)
    id="unique-agent-id",                 # Optional persistent ID
    require_per_service_call_history_persistence=True,  # Required for handoff workflows
)

# Create session for multi-turn conversations
session = agent.create_session()

# Run (single-turn or multi-turn)
result = await agent.run("User message", session=session)
result = await agent.run("User message", session=session, stream=True)

# Access response
result.text          # Final text response
result.messages      # List of Message objects
result.user_input_requests  # Pending approval requests (HITL)
```

### FoundryChatClient — Constructor

```python
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential, DefaultAzureCredential

client = FoundryChatClient(
    project_endpoint="https://your-project.services.ai.azure.com",
    model="gpt-4o",
    credential=AzureCliCredential(),  # or DefaultAzureCredential()
)
```

> **⚠️ PRD uses `FoundryChatClient(endpoint=FOUNDRY_ENDPOINT)` — this is INCORRECT.**
> The correct parameter is `project_endpoint`, and a `credential` + `model` are required.

### @tool Decorator

```python
from typing import Annotated
from agent_framework import tool

@tool(approval_mode="never_require")  # or "always_require" for HITL
def my_function(
    param: Annotated[str, "Description of the parameter"]
) -> str:
    """Tool description shown to the LLM."""
    return f"Result for {param}"
```

---

## 3. Orchestration Patterns

### 3.1 Sequential Workflow

Chain agents in a pipeline — each agent processes the output of the previous one.

```python
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework.orchestrations import SequentialBuilder
from azure.identity import DefaultAzureCredential

client = FoundryChatClient(
    project_endpoint="https://your-project.services.ai.azure.com",
    model="gpt-4o",
    credential=DefaultAzureCredential(),
)

extraction_agent = Agent(
    client=client,
    name="ExtractionAgent",
    instructions="Extract structured data from delivery notes...",
    tools=[blob_mcp, doc_intel_mcp],
)

validation_agent = Agent(
    client=client,
    name="ValidationAgent",
    instructions="Validate extracted data against purchase orders...",
    tools=[cosmos_mcp, bc_read_mcp],
)

workflow = SequentialBuilder(
    participants=[extraction_agent, validation_agent]
).build()

# Run
async for event in workflow.run("Process delivery note X", stream=True):
    if event.type == "output":
        print(event.data)
```

### 3.2 Handoff Workflow (Conditional Routing)

Agents autonomously hand off control based on conversation context.

```python
from agent_framework import Agent
from agent_framework.orchestrations import HandoffBuilder

validation_agent = Agent(
    client=client,
    name="ValidationAgent",
    instructions="""Compare delivery note data with BC purchase orders.
    If match: hand off to InventoryAgent.
    If discrepancy: hand off to EscalationAgent.""",
    tools=[cosmos_mcp, bc_read_mcp],
    require_per_service_call_history_persistence=True,  # REQUIRED for handoff
)

inventory_agent = Agent(
    client=client,
    name="InventoryAgent",
    instructions="Register received goods in Business Central inventory...",
    tools=[bc_write_mcp, cosmos_mcp],
    require_per_service_call_history_persistence=True,
)

escalation_agent = Agent(
    client=client,
    name="EscalationAgent",
    instructions="Notify team via Teams about discrepancies...",
    tools=[teams_mcp, cosmos_mcp],
    require_per_service_call_history_persistence=True,
)

workflow = (
    HandoffBuilder(
        name="validation_workflow",
        participants=[validation_agent, inventory_agent, escalation_agent],
    )
    .with_start_agent(validation_agent)
    .build()
)

result = workflow.run("Validate delivery note DN-2026-001", stream=True)
```

> **⚠️ PRD uses `HandoffWorkflow(agents=[...], handoff_strategy="conditional")` — this is INCORRECT.**
> The correct class is `HandoffBuilder` with `.participants()` and `.with_start_agent()`.build() pattern.
> There is no `handoff_strategy` parameter. Routing is autonomous (agents decide via instructions).

### 3.3 Human-in-the-Loop (HITL)

Two mechanisms:

**A) Tool-level approval (`approval_mode`):**
```python
@tool(approval_mode="always_require")
def update_inventory(item_id: str, quantity: int) -> str:
    """Update inventory — requires human approval."""
    return f"Updated {item_id} with qty {quantity}"

# When agent calls this tool, result.user_input_requests is populated
result = await agent.run("Update inventory for item X")
if result.user_input_requests:
    for req in result.user_input_requests:
        # Show to user, get approval
        approval_msg = req.to_function_approval_response(approved=True)
        result = await agent.run([query, Message("assistant", [req]),
                                  Message("user", [approval_msg])])
```

**B) Handoff to "user" target (Swarm pattern, from AutoGen):**
```python
agent = Agent(
    client=client,
    name="ValidationAgent",
    instructions="If discrepancy found, hand off to 'user' for review.",
    handoffs=["inventory_agent", "user"],  # "user" triggers HITL
)
```

### 3.4 Event-Driven Invocation

MAF agents are invoked programmatically — event-driven behavior comes from the hosting layer:

```python
# Azure Functions hosting
from agent_framework.hosting import AgentFunctionApp

app = AgentFunctionApp(enable_health_check=True)
app.add_agent(extraction_agent)
app.add_agent(validation_agent, enable_mcp_tool_trigger=True)

# Container App / webhook pattern
async def handle_blob_event(event):
    """Called by Event Grid subscription on blob creation."""
    blob_url = event["data"]["url"]
    session = extraction_agent.create_session()
    result = await extraction_agent.run(
        f"Process the delivery note at: {blob_url}",
        session=session
    )
    return result
```

---

## 4. MCP Integration

### Key Insight: NO `McpToolProvider` class exists

The PRD uses `McpToolProvider(server="mcp-blob-storage")` — **this class does not exist** in MAF v1.0.

### Actual MCP Classes

| Class | Transport | Use Case |
|-------|-----------|----------|
| `MCPStreamableHTTPTool` | HTTP/SSE | Remote MCP servers (most common) |
| `MCPStdioTool` | stdio | Local MCP servers via subprocess |

### Usage Pattern

```python
from agent_framework import Agent, MCPStreamableHTTPTool

# Connect to an MCP server over HTTP
blob_mcp = MCPStreamableHTTPTool(
    name="Azure Blob Storage",
    url="https://my-blob-mcp-server.azurecontainerapps.io/mcp",
)

doc_intel_mcp = MCPStreamableHTTPTool(
    name="Document Intelligence",
    url="https://my-docintel-mcp-server.azurecontainerapps.io/mcp",
)

# Use as context manager (recommended for lifecycle management)
async with Agent(
    client=FoundryChatClient(...),
    name="ExtractionAgent",
    instructions="...",
    tools=[blob_mcp, doc_intel_mcp],
) as agent:
    result = await agent.run("Extract data from delivery note")
```

### Alternative: Pass MCP tools at run-time

```python
async with MCPStreamableHTTPTool(
    name="Cosmos DB",
    url="https://cosmos-mcp.azurecontainerapps.io/mcp",
) as cosmos_mcp:
    result = await agent.run("Save to database", tools=cosmos_mcp)
```

### AutoGen Legacy: McpWorkbench (still works)

```python
from autogen_ext.tools.mcp import McpWorkbench, StdioServerParams

server_params = StdioServerParams(
    command="npx",
    args=["@anthropic/mcp-server-fetch"],
)

async with McpWorkbench(server_params=server_params) as workbench:
    agent = AssistantAgent(
        name="web_assistant",
        model_client=model_client,
        workbench=workbench,
    )
```

### Agents AS MCP Servers

MAF agents can be exposed as MCP tools for other agents:

```python
from agent_framework.hosting import AgentFunctionApp

app = AgentFunctionApp(enable_health_check=True)
app.add_agent(stock_agent, enable_mcp_tool_trigger=True)  # Exposes as MCP tool
```

---

## 5. Azure AI Foundry Integration

### FoundryChatClient — Correct Usage

```python
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

client = FoundryChatClient(
    project_endpoint="https://your-project.services.ai.azure.com",
    model="gpt-4o",
    credential=DefaultAzureCredential(),
)
```

### Foundry Toolbox via MCP

Foundry toolboxes can be consumed as MCP endpoints:

```python
from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.foundry import FoundryChatClient

toolbox_mcp = MCPStreamableHTTPTool(
    name="my_toolbox",
    description="Tools served by my Foundry toolbox",
    url="https://<your-toolbox-mcp-endpoint>",
)

async with Agent(
    client=FoundryChatClient(...),
    tools=[toolbox_mcp],
) as agent:
    result = await agent.run("What tools are available?")
```

### Deployment to Foundry

- Use `azd` (Azure Developer CLI) for deployment
- Agents can be hosted on Azure Functions via `AgentFunctionApp`
- CI/CD via GitHub Actions with service principal auth
- Foundry provides model catalog, evaluation tools, and monitoring

### Azure Monitor Integration from FoundryChatClient

```python
# Foundry-native monitoring setup
await client.configure_azure_monitor(enable_live_metrics=True)
```

---

## 6. Telemetry & Observability

### OpenTelemetry — Built-in Support

```python
from agent_framework.observability import configure_otel_providers, get_tracer

# Option 1: Environment variable-based (simplest)
# Set OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_SERVICE_NAME, etc.
configure_otel_providers(enable_sensitive_data=True)

# Option 2: Azure Monitor (Application Insights)
from azure.monitor.opentelemetry import configure_azure_monitor
from agent_framework.observability import create_resource, enable_instrumentation

configure_azure_monitor(
    connection_string="InstrumentationKey=...",
    resource=create_resource(),
    enable_live_metrics=True,
)
enable_instrumentation(enable_sensitive_data=False)

# Option 3: Foundry-native
client = FoundryChatClient(...)
await client.configure_azure_monitor(enable_live_metrics=True)
```

### Custom Spans

```python
from agent_framework.observability import get_tracer
from opentelemetry.trace import SpanKind

with get_tracer().start_as_current_span("ProcessDeliveryNote", kind=SpanKind.CLIENT) as span:
    result = await agent.run("Process delivery note", session=session)
```

### GenAI Semantic Conventions

MAF v1.0 supports OpenTelemetry GenAI semantic conventions, meaning traces include:
- Model name, token usage (input/output)
- Tool calls and results
- Agent handoff events
- Session/conversation IDs

### Dependencies for Observability

```bash
pip install opentelemetry-sdk opentelemetry-exporter-otlp
pip install azure-monitor-opentelemetry  # For Application Insights
```

---

## 7. PRD Pseudocode Validation

### Section 4.4 (Flow 1 — Event-Driven Single Agent)

| PRD Code | Status | Correct Code |
|----------|--------|-------------|
| `from agent_framework import Agent, FoundryChatClient` | ❌ Wrong import | `from agent_framework import Agent` + `from agent_framework.foundry import FoundryChatClient` |
| `from agent_framework.tools import McpToolProvider` | ❌ Class doesn't exist | `from agent_framework import MCPStreamableHTTPTool` |
| `McpToolProvider(server="mcp-blob-storage")` | ❌ Wrong API | `MCPStreamableHTTPTool(name="Blob Storage", url="https://...")` |
| `FoundryChatClient(endpoint=FOUNDRY_ENDPOINT)` | ❌ Wrong params | `FoundryChatClient(project_endpoint=..., model=..., credential=...)` |
| `Agent(client=..., name=..., instructions=..., tools=[...])` | ✅ Correct pattern | Same, but add `async with` context manager |
| `await extraction_agent.run(f"...")` | ✅ Correct pattern | Same |

**Corrected Flow 1:**

```python
import asyncio
from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

MCP_BASE = "https://mcp-servers.azurecontainerapps.io"

blob_mcp = MCPStreamableHTTPTool(name="Blob Storage", url=f"{MCP_BASE}/blob/mcp")
cosmos_mcp = MCPStreamableHTTPTool(name="Cosmos DB", url=f"{MCP_BASE}/cosmos/mcp")
doc_intel_mcp = MCPStreamableHTTPTool(name="Document Intelligence", url=f"{MCP_BASE}/docintel/mcp")

client = FoundryChatClient(
    project_endpoint="https://verdecora-ai.services.ai.azure.com",
    model="gpt-4o",
    credential=DefaultAzureCredential(),
)

extraction_agent = Agent(
    client=client,
    name="ExtractionAgent",
    instructions="""Eres un agente experto en lectura de albaranes de entrega.
    Analiza la imagen proporcionada y extrae TODOS los campos relevantes
    en formato JSON estructurado: proveedor, fecha, nº albarán,
    líneas de detalle (producto, cantidad, unidad, precio), totales,
    observaciones, y referencia al pedido si existe.""",
    tools=[blob_mcp, doc_intel_mcp, cosmos_mcp],
)

async def handle_blob_event(event):
    """Webhook handler for Event Grid blob-created events."""
    blob_url = event["data"]["url"]
    async with extraction_agent as agent:
        session = agent.create_session()
        result = await agent.run(
            f"Procesa el albarán ubicado en: {blob_url}",
            session=session,
        )
    return result
```

### Section 4.5 (Flow 2 — Sequential + Handoff)

| PRD Code | Status | Correct Code |
|----------|--------|-------------|
| `from agent_framework import HandoffWorkflow` | ❌ Class doesn't exist | `from agent_framework.orchestrations import HandoffBuilder` |
| `HandoffWorkflow(agents=[...], handoff_strategy="conditional")` | ❌ Wrong API | `HandoffBuilder(participants=[...]).with_start_agent(...).build()` |
| `await workflow.run(f"...")` | ⚠️ Partially correct | Use `async for event in workflow.run(..., stream=True):` for streaming |

**Corrected Flow 2:**

```python
from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.foundry import FoundryChatClient
from agent_framework.orchestrations import HandoffBuilder
from azure.identity import DefaultAzureCredential

MCP_BASE = "https://mcp-servers.azurecontainerapps.io"

bc_read_mcp = MCPStreamableHTTPTool(name="BC Read", url=f"{MCP_BASE}/bc-read/mcp")
bc_write_mcp = MCPStreamableHTTPTool(name="BC Inventory", url=f"{MCP_BASE}/bc-write/mcp")
cosmos_mcp = MCPStreamableHTTPTool(name="Cosmos DB", url=f"{MCP_BASE}/cosmos/mcp")
teams_mcp = MCPStreamableHTTPTool(name="Teams Notifications", url=f"{MCP_BASE}/teams/mcp")

client = FoundryChatClient(
    project_endpoint="https://verdecora-ai.services.ai.azure.com",
    model="gpt-4o",
    credential=DefaultAzureCredential(),
)

validation_agent = Agent(
    client=client,
    name="ValidationAgent",
    instructions="""Comparas datos de albaranes extraídos con pedidos
    de Business Central. Identifica discrepancias en: cantidades,
    productos, precios, referencias. Emite un veredicto estructurado.
    Si coincide: hand off a InventoryAgent.
    Si hay discrepancias: hand off a EscalationAgent.""",
    tools=[cosmos_mcp, bc_read_mcp],
    require_per_service_call_history_persistence=True,
)

inventory_agent = Agent(
    client=client,
    name="InventoryAgent",
    instructions="""Registras mercancía recibida en el inventario de
    Business Central. Solo realizas operaciones de ALTA (Create/Update).
    Nunca eliminas registros.""",
    tools=[bc_write_mcp, cosmos_mcp],
    require_per_service_call_history_persistence=True,
)

escalation_agent = Agent(
    client=client,
    name="EscalationAgent",
    instructions="""Notificas al equipo por Teams sobre discrepancias
    encontradas en la validación del albarán. Incluye detalles de
    las diferencias para revisión humana.""",
    tools=[teams_mcp, cosmos_mcp],
    require_per_service_call_history_persistence=True,
)

workflow = (
    HandoffBuilder(
        name="validation_workflow",
        participants=[validation_agent, inventory_agent, escalation_agent],
    )
    .with_start_agent(validation_agent)
    .build()
)

async def handle_change_feed(document):
    """Cosmos DB Change Feed processor."""
    async for event in workflow.run(
        f"Valida el albarán {document['id']} contra su pedido "
        f"referencia {document['ref_pedido']} y procede según resultado.",
        stream=True,
    ):
        if event.type == "output":
            # Log or process the output
            pass
```

---

## 8. Recommendations for Our Project

### Architecture Decisions

1. **Use `agent-framework` v1.0+ (not AutoGen or SK directly)**
   - Single unified SDK, production-ready, long-term support
   - All orchestration patterns we need are built-in

2. **MCP servers should use Streamable HTTP transport**
   - Use `MCPStreamableHTTPTool` for all MCP connections
   - Each MCP server deployed as a Container App with `/mcp` endpoint
   - No `McpToolProvider` class — update all design docs

3. **HandoffBuilder for conditional routing (not HandoffWorkflow)**
   - Agents decide routing autonomously via their instructions
   - Add `require_per_service_call_history_persistence=True` to all handoff agents
   - No `handoff_strategy` parameter needed

4. **FoundryChatClient requires 3 params**: `project_endpoint`, `model`, `credential`
   - Use `DefaultAzureCredential()` for production (supports managed identity)
   - Use `AzureCliCredential()` for local development

5. **HITL via `approval_mode="always_require"` on sensitive tools**
   - For Teams escalation, combine with handoff to "user" target
   - The `user_input_requests` mechanism is built into `AgentResponse`

6. **Observability from day 1**
   - Use `configure_azure_monitor()` + `enable_instrumentation()`
   - Wrap workflows in custom spans via `get_tracer()`
   - GenAI semantic conventions auto-emit token counts, model info

7. **Azure Functions hosting via `AgentFunctionApp`**
   - Can expose agents as both HTTP endpoints and MCP tool triggers
   - Good fit for event-driven architecture (Event Grid → Functions)

### Critical PRD Corrections Needed

| Issue | PRD Says | Should Be |
|-------|----------|-----------|
| Import path | `from agent_framework import FoundryChatClient` | `from agent_framework.foundry import FoundryChatClient` |
| MCP class | `McpToolProvider(server="...")` | `MCPStreamableHTTPTool(name="...", url="...")` |
| Foundry client | `FoundryChatClient(endpoint=...)` | `FoundryChatClient(project_endpoint=..., model=..., credential=...)` |
| Handoff class | `HandoffWorkflow(agents=[], handoff_strategy="conditional")` | `HandoffBuilder(participants=[...]).with_start_agent(...).build()` |
| Workflow run | `await workflow.run(...)` | `async for event in workflow.run(..., stream=True):` |

### Dependency List for `requirements.txt`

```txt
agent-framework>=1.0.0
azure-identity>=1.17.0
azure-monitor-opentelemetry>=1.6.0
opentelemetry-sdk>=1.25.0
opentelemetry-exporter-otlp>=1.25.0
```

---

*Research completed 2026-05-03 by Ash (MAF Specialist)*
