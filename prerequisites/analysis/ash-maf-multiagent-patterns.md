# MAF v1.0+ Multi-Agent Orchestration Patterns

**Author:** Ash (MAF Specialist)
**Date:** 2026-05-04
**Status:** Complete
**Sources:** Context7 (microsoft/agent-framework, samples), web search, Azure documentation, DeepWiki

---

## 1. Orchestration Patterns Overview

MAF v1.0 GA provides **6 orchestration patterns** via `agent_framework.orchestrations`, plus a low-level `WorkflowBuilder` for custom graphs:

| # | Pattern | Builder Class | Description |
|---|---------|---------------|-------------|
| 1 | **Sequential** | `SequentialBuilder` | Ordered agent pipeline — each agent processes the previous one's output |
| 2 | **Handoff** | `HandoffBuilder` | Decentralized agent mesh — agents autonomously route to each other |
| 3 | **Concurrent** | `ConcurrentBuilder` | Fan-out/fan-in — all agents process same input in parallel |
| 4 | **Group Chat** | `GroupChatBuilder` | Multi-agent conversation with selection function (round-robin or LLM-based) |
| 5 | **Magentic One** | `MagenticBuilder` | Supervisor/manager pattern — LLM-managed dynamic orchestration |
| 6 | **Custom Graph** | `WorkflowBuilder` | Low-level DAG with conditional edges, supersteps, checkpointing |

### Import

```python
from agent_framework.orchestrations import (
    SequentialBuilder,
    ConcurrentBuilder,
    HandoffBuilder,
    GroupChatBuilder,
    MagenticBuilder,
)
from agent_framework import WorkflowBuilder  # For custom graph workflows
```

---

## 2. Pattern Details

### 2.1 Sequential (SequentialBuilder)

**What:** Chain agents in a fixed pipeline. Output of agent N feeds agent N+1.

**When to use:** ETL pipelines, staged document processing, deterministic multi-step workflows.

**Constraints:**
- In-process only (all agents in same Python process)
- Fixed order — no conditional branching
- State flows linearly via conversation messages

**Code:**
```python
from agent_framework.orchestrations import SequentialBuilder

workflow = SequentialBuilder(
    participants=[extraction_agent, validation_agent, posting_agent]
).build()

# Run
async for event in workflow.run("Process delivery note DN-001", stream=True):
    if event.type == "output":
        print(event.data)
```

**State flow:** Each agent receives the full conversation history from previous agents. Output messages are appended to the conversation and passed to the next agent.

---

### 2.2 Handoff (HandoffBuilder)

**What:** Decentralized agent routing. Agents autonomously decide which agent to hand off to next, based on conversation context and their instructions.

**When to use:** Triage/routing, escalation flows, specialist chaining where the path isn't predetermined.

**Constraints:**
- In-process only
- All participants must set `require_per_service_call_history_persistence=True`
- Routing is LLM-driven (agents decide via instructions, no explicit routing table)
- Full conversation history preserved across handoffs (including `Message.additional_properties`)

**Code:**
```python
from agent_framework.orchestrations import HandoffBuilder

workflow = (
    HandoffBuilder(
        name="albaran_workflow",
        participants=[triage_agent, extraction_agent, validation_agent, escalation_agent],
        termination_condition=lambda conv: len(conv) > 0 and "COMPLETE" in conv[-1].text,
    )
    .with_start_agent(triage_agent)
    .build()
)

result = workflow.run("Process delivery note DN-001", stream=True)
```

**Explicit handoff targets (optional):**
```python
# Restrict which agents can hand off to which
workflow = (
    HandoffBuilder(name="support")
    .participants([triage, billing, returns])
    .with_start_agent(triage)
    .add_handoff(source=triage, targets=[billing, returns])
    .add_handoff(source=billing, targets=[triage])
    .add_handoff(source=returns, targets=[triage])
    .build()
)
```

**HITL via handoff to "user":**
```python
agent = Agent(
    client=client,
    name="ValidationAgent",
    instructions="If discrepancy found, hand off to 'user' for review.",
    handoffs=["inventory_agent", "user"],  # "user" triggers HITL pause
    require_per_service_call_history_persistence=True,
)
```

**State flow:** Full conversation history (all messages from all agents) flows through the handoff chain. Each agent sees everything that happened before.

---

### 2.3 Concurrent (ConcurrentBuilder)

**What:** Fan-out to multiple agents in parallel, then aggregate results.

**When to use:** Getting multiple perspectives, parallel validation checks, batch processing.

**Constraints:**
- In-process only
- All agents receive the SAME input (fan-out)
- Each agent runs independently with its own session
- Results are aggregated into a list

**Code:**
```python
from agent_framework.orchestrations import ConcurrentBuilder

workflow = ConcurrentBuilder(
    participants=[format_checker, quantity_checker, price_checker]
).build()

events = await workflow.run("Validate delivery note data: {...}")
outputs = events.get_outputs()
for output in outputs:
    for msg in output:
        print(f"[{msg.author_name}]: {msg.text}")
```

**State flow:** No state sharing between parallel agents. Each gets the original input independently. Results are collected after all complete.

---

### 2.4 Group Chat (GroupChatBuilder)

**What:** Multi-agent conversation where a selection function decides who speaks next.

**When to use:** Collaborative review, debate/consensus, iterative refinement where agents build on each other's output.

**Constraints:**
- In-process only
- Requires a `selection_func` (round-robin, LLM-based, or custom)
- Needs a `termination_condition` to stop the conversation
- All agents share the same conversation thread

**Code:**
```python
from agent_framework.orchestrations import GroupChatBuilder, GroupChatState

def round_robin_selector(state: GroupChatState) -> str:
    names = list(state.participants.keys())
    return names[state.current_round % len(names)]

workflow = GroupChatBuilder(
    participants=[expert_agent, verifier_agent, clarifier_agent],
    termination_condition=lambda conversation: len(conversation) >= 6,
    intermediate_outputs=True,
    selection_func=round_robin_selector,
).build()

async for event in workflow.run("Review extraction results for DN-001", stream=True):
    if event.type == "output":
        print(f"{event.data.author_name}: {event.data.text}")
```

**LLM-based selection:** Instead of round-robin, pass a function that uses an LLM to pick the next speaker based on conversation context. This maps to AutoGen's `SelectorGroupChat`.

**State flow:** Shared conversation thread. All agents see all previous messages from all participants.

---

### 2.5 Magentic One / Supervisor (MagenticBuilder)

**What:** An LLM-managed supervisor/manager agent that dynamically decides which participant agent to invoke next, can re-plan, and handles complex open-ended tasks.

**When to use:** Complex workflows requiring dynamic routing, open-ended tasks where the path isn't predetermined, when you need a "supervisor" deciding who acts next.

**Constraints:**
- In-process only
- Requires a manager agent (LLM-based or custom)
- `max_round_count` and `max_stall_count` prevent infinite loops
- Supports checkpointing and HITL plan review
- Higher token cost (manager agent reasons about each step)

**Code:**
```python
from agent_framework.orchestrations import MagenticBuilder

workflow = MagenticBuilder(
    participants=[
        extraction_agent,
        validation_agent,
        escalation_agent,
        posting_agent,
        notification_agent,
    ],
    manager_agent=manager_agent,  # LLM-based supervisor
).build()

async for message in workflow.run("Process and register delivery note DN-001"):
    print(message.text)
```

**With StandardMagenticManager:**
```python
from agent_framework.orchestrations import MagenticBuilder

workflow = (
    MagenticBuilder()
    .participants(
        extractor=extraction_agent,
        validator=validation_agent,
        poster=posting_agent,
        escalator=escalation_agent,
        notifier=notification_agent,
    )
    .with_standard_manager(
        chat_client=client,
        max_round_count=20,
        max_stall_count=3,
    )
    .with_plan_review(enable=True)       # HITL: human reviews the plan
    .with_checkpointing(checkpoint_storage)  # Persist state for resume
    .build()
)
```

**Custom Manager:**
```python
from agent_framework.orchestrations import MagenticManagerBase, MagenticContext

class AlbaranSupervisor(MagenticManagerBase):
    async def plan(self, context: MagenticContext) -> ChatMessage:
        # Custom logic: examine conversation, decide next agent
        if "discrepancy" in context.last_message.text.lower():
            return context.route_to("escalator")
        elif "extracted" in context.last_message.text.lower():
            return context.route_to("validator")
        else:
            return context.route_to("extractor")
```

**State flow:** Manager agent maintains plan and conversation context. Full history available to manager for decision-making. Individual agents see conversation relevant to their invocation.

---

### 2.6 Custom Graph (WorkflowBuilder)

**What:** Low-level workflow graph builder with conditional edges, switch/case routing, checkpointing, and durable execution support.

**When to use:** When none of the higher-level patterns fit. Complex DAGs with conditional branching, loops, fan-out/fan-in, and HITL pause points.

**Constraints:**
- Most flexible pattern
- Can be hosted in Azure Functions (`AgentFunctionApp`) for durable execution
- Supports `CosmosCheckpointStorage` for state persistence across restarts
- Supports conditional edges and switch/case routing

**Code:**
```python
from agent_framework import WorkflowBuilder, AgentExecutor

# Create executors from agents
extraction_exec = AgentExecutor(extraction_agent, id="extraction")
validation_exec = AgentExecutor(validation_agent, id="validation")
posting_exec = AgentExecutor(posting_agent, id="posting")
escalation_exec = AgentExecutor(escalation_agent, id="escalation")
notification_exec = AgentExecutor(notification_agent, id="notification")

# Define conditions
def is_valid(result) -> bool:
    return "VALID" in str(result).upper()

def is_discrepancy(result) -> bool:
    return "DISCREPANCY" in str(result).upper()

# Build the graph
from agent_framework import Case, Default

workflow = (
    WorkflowBuilder()
    .set_start_executor(extraction_exec)
    .add_edge(extraction_exec, validation_exec)
    .add_switch_case_edge_group(
        validation_exec,
        [
            Case(condition=is_valid, target=posting_exec),
            Case(condition=is_discrepancy, target=escalation_exec),
            Default(target=notification_exec),
        ],
    )
    .add_edge(posting_exec, notification_exec)
    .add_edge(escalation_exec, notification_exec)
    .build()
)

result = await workflow.run(message="Process DN-001")
```

**With checkpointing (durable, resumable):**
```python
from agent_framework_azure_cosmos import CosmosCheckpointStorage
from azure.identity.aio import DefaultAzureCredential

checkpoint_storage = CosmosCheckpointStorage(
    endpoint="https://verdecora-cosmos.documents.azure.com:443/",
    credential=DefaultAzureCredential(),
    database_name="agent-framework",
    container_name="workflow-checkpoints",
)

workflow = WorkflowBuilder(
    start_executor=extraction_exec,
    checkpoint_storage=checkpoint_storage,
).build()

# Run — checkpoints saved after each superstep
result = await workflow.run(message="Process DN-001")

# Resume from last checkpoint (after crash/restart/HITL wait)
latest = await checkpoint_storage.get_latest(workflow_name=workflow.name)
if latest:
    resumed = await workflow.run(checkpoint_id=latest.checkpoint_id)
```

---

## 3. Cross-Process Communication: A2A Protocol

### Key Insight: In-process orchestration vs. cross-process A2A

All the above patterns (Sequential, Handoff, GroupChat, Magentic, Concurrent) are **in-process** — all agents run in the same Python process. For **cross-container** communication (agents in different ACA containers), MAF supports the **A2A (Agent-to-Agent) protocol**.

### A2A Protocol

| Feature | Details |
|---------|---------|
| **Package** | `agent-framework-a2a` (Python) |
| **Transport** | HTTP/JSON-RPC, supports streaming via SSE |
| **Discovery** | Agent Cards (metadata + capability descriptions) |
| **Standard** | Open standard, interoperable with Google ADK, CrewAI, LangGraph |

### Exposing an Agent via A2A (Server)

```python
from agent_framework.a2a import A2AServer
from fastapi import FastAPI

app = FastAPI()
a2a_server = A2AServer(agent=my_agent)
a2a_server.mount(app, path="/a2a")

# Other agents can now invoke this agent at:
# https://my-agent.azurecontainerapps.io/a2a
```

### Invoking a Remote Agent via A2A (Client)

```python
from agent_framework.a2a import A2AAgent

remote_agent = A2AAgent(url="https://validation-agent.azurecontainerapps.io/a2a")
result = await remote_agent.run("Validate delivery note DN-001")
```

### Architecture for our project

```
┌─────────────────────────────────────────────────────────────────┐
│                    ACA Environment (VNet)                        │
│                                                                 │
│  ┌──────────┐   A2A   ┌──────────┐   A2A   ┌──────────┐       │
│  │ Ingestion│────────→│Validation│────────→│ Posting  │       │
│  │  Agent   │         │  Agent   │         │  Agent   │       │
│  │  (ACA)   │         │  (ACA)   │         │  (ACA)   │       │
│  └──────────┘         └────┬─────┘         └──────────┘       │
│                            │ A2A                               │
│                       ┌────▼─────┐         ┌──────────┐       │
│                       │Escalation│────────→│  Notif   │       │
│                       │  Agent   │  A2A    │  Agent   │       │
│                       │  (ACA)   │         │  (ACA)   │       │
│                       └──────────┘         └──────────┘       │
│                                                                 │
│  ┌──────────┐  Cosmos DB checkpoint storage (shared)           │
│  │Supervisor│  orchestrates A2A calls between agents           │
│  │  Agent   │                                                  │
│  │  (ACA)   │                                                  │
│  └──────────┘                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Project-Specific Questions

### 4.1 How would MAF handle a pipeline with 5-8 agents?

**Two approaches:**

**A) Single-process with MagenticBuilder (simpler, recommended to start):**
- All 5-8 agents in ONE ACA container
- MagenticBuilder supervisor decides routing
- Lower latency, simpler deployment
- Limitation: single container resource constraints

```python
workflow = (
    MagenticBuilder()
    .participants(
        ingestion=ingestion_agent,
        extraction=extraction_agent,
        validation=validation_agent,
        escalation=escalation_agent,
        posting=posting_agent,
        notification=notification_agent,
        audit=audit_agent,
        hitl=hitl_agent,
    )
    .with_standard_manager(chat_client=client, max_round_count=30)
    .with_checkpointing(cosmos_checkpoint_storage)
    .build()
)
```

**B) Multi-process with A2A + Supervisor ACA (more scalable):**
- Each agent in its own ACA container
- Supervisor agent (in its own ACA) orchestrates via A2A calls
- Each agent scales independently
- Higher latency (HTTP calls between agents)
- More complex deployment but better fault isolation

**Recommendation for our project (750 albaranes/day peak):** Start with approach A (single process). At our volume, a single ACA container with 2-4 vCPU can handle this. Move to approach B only if we need independent scaling or fault isolation.

### 4.2 Can MAF do dynamic routing (supervisor decides)?

**Yes — MagenticBuilder is exactly this.** The `StandardMagenticManager` uses an LLM to:
1. Create a plan for which agents to invoke
2. Execute the plan step by step
3. Re-plan if something unexpected happens
4. Decide when the task is complete

You can also implement a `MagenticManagerBase` subclass for deterministic (non-LLM) routing logic.

### 4.3 How does MAF handle long waits (24h HITL) without Durable Functions?

**Three mechanisms:**

**A) WorkflowBuilder + CosmosCheckpointStorage (recommended):**
```python
# Workflow checkpoints state to Cosmos after each superstep
# When HITL is needed:
# 1. Workflow reaches a point where it needs human input
# 2. State is checkpointed to Cosmos DB
# 3. Process can terminate / scale to zero
# 4. When human responds (via email webhook), resume:

latest = await checkpoint_storage.get_latest(workflow_name="albaran-workflow")
if latest:
    result = await workflow.run(checkpoint_id=latest.checkpoint_id)
```

**B) AgentSession serialization (manual):**
```python
# Serialize session state to any store
session_data = session.to_dict()
json_str = json.dumps(session_data)
# Store in Cosmos DB, Redis, etc.

# Hours/days later, deserialize and resume:
data = json.loads(stored_json)
session = AgentSession.from_dict(data)
result = await agent.run("Human approved: proceed with posting", session=session)
```

**C) Event-driven pattern (our recommended architecture):**
```
1. Agent processes albaran → needs HITL approval
2. Agent saves state to Cosmos + sends email via WorkIQ
3. ACA container can scale to zero (no resources consumed during 24h wait)
4. Human clicks approve/reject in email
5. Email response triggers webhook → Event Grid → ACA
6. New ACA instance loads state from Cosmos → resumes workflow
```

This is **more efficient than Durable Functions** for our use case because:
- No idle compute during HITL wait (ACA scales to zero)
- State in Cosmos DB (durable, queryable)
- Natural fit with email-based HITL pattern

### 4.4 Can MAF agents communicate via Service Bus?

**Not natively** — MAF doesn't have a Service Bus transport built-in. But integration is straightforward:

```python
from azure.servicebus.aio import ServiceBusClient, ServiceBusSender

# Agent sends message to Service Bus queue
@tool(approval_mode="never_require")
async def send_to_validation_queue(
    albaran_data: Annotated[str, "JSON albaran data to validate"]
) -> str:
    """Send albaran data to the validation queue."""
    async with ServiceBusClient.from_connection_string(conn_str) as client:
        sender = client.get_queue_sender(queue_name="validation-queue")
        async with sender:
            await sender.send_messages(ServiceBusMessage(albaran_data))
    return "Sent to validation queue"

# Receiving side: ACA container with Service Bus trigger
# Uses KEDA scaler for Service Bus queue length
async def process_validation_message(message_body: str):
    session = validation_agent.create_session()
    result = await validation_agent.run(message_body, session=session)
    # ... handle result
```

**However**, for our project, **A2A is simpler** for agent-to-agent communication. Service Bus is better suited for:
- Decoupling producers/consumers with different lifecycles
- Guaranteed delivery with dead-letter handling
- Load leveling during peak periods

### 4.5 How does MAF integrate with external events?

**MAF agents are invoked programmatically** — event-driven behavior comes from the hosting layer:

**A) Azure Functions hosting with event triggers:**
```python
from agent_framework.hosting import AgentFunctionApp

app = AgentFunctionApp(workflow=my_workflow, enable_health_check=True)

# Azure Functions handles blob triggers, Event Grid, Service Bus, etc.
# The AgentFunctionApp wraps the workflow for function invocation
```

**B) FastAPI + Event Grid webhooks (ACA pattern):**
```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/events/blob-created")
async def handle_blob_created(request: Request):
    """Event Grid subscription: blob created in 'albaranes' container."""
    events = await request.json()
    for event in events:
        blob_url = event["data"]["url"]
        session = ingestion_agent.create_session()
        result = await ingestion_agent.run(
            f"New delivery note uploaded: {blob_url}",
            session=session,
        )
    return {"status": "processed"}

@app.post("/events/hitl-response")
async def handle_hitl_response(request: Request):
    """Webhook: human responded to HITL email."""
    data = await request.json()
    workflow_id = data["workflow_id"]
    decision = data["decision"]  # "approved" / "rejected" / "modified"

    # Resume workflow from checkpoint
    latest = await checkpoint_storage.get_latest(workflow_name=workflow_id)
    if latest:
        result = await workflow.run(
            checkpoint_id=latest.checkpoint_id,
            message=f"Human decision: {decision}",
        )
    return {"status": "resumed"}
```

---

## 5. Practical Code Examples

### 5.1 Five-Agent Pipeline with MagenticBuilder (Supervisor Pattern)

```python
"""
Albaran processing pipeline with 5 agents + supervisor.
All agents in a single ACA container.
"""
import asyncio
from agent_framework import Agent, tool, MCPStreamableHTTPTool
from agent_framework.foundry import FoundryChatClient
from agent_framework.orchestrations import MagenticBuilder
from agent_framework_azure_cosmos import CosmosCheckpointStorage
from azure.identity.aio import DefaultAzureCredential

credential = DefaultAzureCredential()

client = FoundryChatClient(
    project_endpoint="https://verdecora-ai.services.ai.azure.com",
    model="gpt-5.1",
    credential=credential,
)

# MCP tools (remote servers in other ACA containers)
blob_mcp = MCPStreamableHTTPTool(
    name="Azure Blob Storage",
    url="https://mcp-blob.internal.azurecontainerapps.io/mcp",
)
docintel_mcp = MCPStreamableHTTPTool(
    name="Document Intelligence",
    url="https://mcp-docintel.internal.azurecontainerapps.io/mcp",
)
cosmos_mcp = MCPStreamableHTTPTool(
    name="Cosmos DB",
    url="https://mcp-cosmos.internal.azurecontainerapps.io/mcp",
)
bc_mcp = MCPStreamableHTTPTool(
    name="Business Central",
    url="https://mcp-bc.internal.azurecontainerapps.io/mcp",
)

# Agent definitions
ingestion_agent = Agent(
    client=client,
    name="IngestionAgent",
    instructions="""You receive blob URLs of delivery note PDFs.
    Use Document Intelligence to extract text and structured data.
    Output a JSON with: supplier, date, albaran_number, line_items[].""",
    tools=[blob_mcp, docintel_mcp],
)

validation_agent = Agent(
    client=client,
    name="ValidationAgent",
    instructions="""Compare extracted albaran data against Business Central PO.
    Check: supplier exists, PO number exists, quantities within 2% tolerance,
    prices match. Output: VALID or DISCREPANCY with details.""",
    tools=[cosmos_mcp, bc_mcp],
)

escalation_agent = Agent(
    client=client,
    name="EscalationAgent",
    instructions="""Handle discrepancies found during validation.
    Save discrepancy details to Cosmos DB.
    Prepare HITL notification with approve/reject/modify options.""",
    tools=[cosmos_mcp],
)

posting_agent = Agent(
    client=client,
    name="PostingAgent",
    instructions="""Post validated albaran to Business Central.
    Create purchase receipt, update inventory quantities.
    Output: BC posting confirmation with document number.""",
    tools=[bc_mcp, cosmos_mcp],
)

notification_agent = Agent(
    client=client,
    name="NotificationAgent",
    instructions="""Send processing result notifications.
    Update albaran status in Cosmos DB.
    For successful postings: notify store manager.
    For escalations: send HITL email via WorkIQ.""",
    tools=[cosmos_mcp],
)

# Checkpoint storage for durable execution
checkpoint_storage = CosmosCheckpointStorage(
    endpoint="https://verdecora-cosmos.documents.azure.com:443/",
    credential=credential,
    database_name="verdecora-agents",
    container_name="workflow-checkpoints",
)

# Build supervisor workflow
workflow = (
    MagenticBuilder()
    .participants(
        ingestion=ingestion_agent,
        validation=validation_agent,
        escalation=escalation_agent,
        posting=posting_agent,
        notification=notification_agent,
    )
    .with_standard_manager(
        chat_client=client,
        max_round_count=20,
        max_stall_count=3,
    )
    .with_checkpointing(checkpoint_storage)
    .build()
)

async def process_albaran(blob_url: str):
    async for event in workflow.run(
        f"Process delivery note at: {blob_url}",
        stream=True,
    ):
        if event.type == "output":
            print(f"[{event.data.author_name}]: {event.data.text}")

if __name__ == "__main__":
    asyncio.run(process_albaran("https://verdecora.blob.core.windows.net/albaranes/DN-001.pdf"))
```

### 5.2 Handoff Chain with Conditional Routing

```python
"""
Handoff-based workflow: agents decide routing autonomously.
Triage → Extraction → Validation → (Posting | Escalation) → Notification
"""
from agent_framework import Agent
from agent_framework.orchestrations import HandoffBuilder

# All agents need this for handoff
HANDOFF_OPTS = {"require_per_service_call_history_persistence": True}

triage_agent = Agent(
    client=client,
    name="TriageAgent",
    instructions="""You are the entry point for albaran processing.
    Determine the type of incoming request:
    - New albaran PDF: hand off to ExtractionAgent
    - HITL response (approval/rejection): hand off to PostingAgent or EscalationAgent
    - Status query: respond directly""",
    **HANDOFF_OPTS,
)

extraction_agent = Agent(
    client=client,
    name="ExtractionAgent",
    instructions="""Extract structured data from delivery note.
    After extraction, hand off to ValidationAgent with the extracted JSON.""",
    tools=[blob_mcp, docintel_mcp],
    **HANDOFF_OPTS,
)

validation_agent = Agent(
    client=client,
    name="ValidationAgent",
    instructions="""Compare extracted data with BC purchase orders.
    If VALID (all checks pass): hand off to PostingAgent.
    If DISCREPANCY found: hand off to EscalationAgent.
    Always include validation details in your message.""",
    tools=[cosmos_mcp, bc_mcp],
    **HANDOFF_OPTS,
)

posting_agent = Agent(
    client=client,
    name="PostingAgent",
    instructions="""Post validated albaran to Business Central.
    After posting, hand off to NotificationAgent with the BC document number.""",
    tools=[bc_mcp, cosmos_mcp],
    **HANDOFF_OPTS,
)

escalation_agent = Agent(
    client=client,
    name="EscalationAgent",
    instructions="""Handle discrepancies. Save to Cosmos and prepare HITL request.
    Hand off to NotificationAgent to send the HITL email.""",
    tools=[cosmos_mcp],
    **HANDOFF_OPTS,
)

notification_agent = Agent(
    client=client,
    name="NotificationAgent",
    instructions="""Send final notifications. Update status in Cosmos.
    Do NOT hand off to any other agent — you are the terminal agent.
    Include 'WORKFLOW_COMPLETE' in your final message.""",
    tools=[cosmos_mcp],
    **HANDOFF_OPTS,
)

workflow = (
    HandoffBuilder(
        name="albaran_handoff",
        participants=[
            triage_agent, extraction_agent, validation_agent,
            posting_agent, escalation_agent, notification_agent,
        ],
        termination_condition=lambda conv: (
            len(conv) > 0 and "WORKFLOW_COMPLETE" in conv[-1].text
        ),
    )
    .with_start_agent(triage_agent)
    .add_handoff(source=triage_agent, targets=[extraction_agent, posting_agent, escalation_agent])
    .add_handoff(source=extraction_agent, targets=[validation_agent])
    .add_handoff(source=validation_agent, targets=[posting_agent, escalation_agent])
    .add_handoff(source=posting_agent, targets=[notification_agent])
    .add_handoff(source=escalation_agent, targets=[notification_agent])
    .build()
)
```

### 5.3 Pause/Resume Workflow for HITL (24h wait)

```python
"""
WorkflowBuilder pattern with checkpointing for long HITL waits.
This is the recommended approach for 24h email-based HITL.
"""
import json
from agent_framework import WorkflowBuilder, AgentExecutor, Case, Default
from agent_framework_azure_cosmos import CosmosCheckpointStorage
from fastapi import FastAPI, Request

app = FastAPI()

# Checkpoint storage
checkpoint_storage = CosmosCheckpointStorage(
    endpoint="https://verdecora-cosmos.documents.azure.com:443/",
    credential=credential,
    database_name="verdecora-agents",
    container_name="workflow-checkpoints",
)

# Executors
extract_exec = AgentExecutor(extraction_agent, id="extract")
validate_exec = AgentExecutor(validation_agent, id="validate")
post_exec = AgentExecutor(posting_agent, id="post")
escalate_exec = AgentExecutor(escalation_agent, id="escalate")
notify_exec = AgentExecutor(notification_agent, id="notify")

# Conditions
def is_valid(result) -> bool:
    return "VALID" in str(result).upper()

def needs_hitl(result) -> bool:
    return "DISCREPANCY" in str(result).upper()

# Build durable workflow
workflow = (
    WorkflowBuilder(checkpoint_storage=checkpoint_storage)
    .set_start_executor(extract_exec)
    .add_edge(extract_exec, validate_exec)
    .add_switch_case_edge_group(
        validate_exec,
        [
            Case(condition=is_valid, target=post_exec),
            Case(condition=needs_hitl, target=escalate_exec),
        ],
    )
    .add_edge(post_exec, notify_exec)
    .add_edge(escalate_exec, notify_exec)  # After sending HITL email, checkpoint here
    .build()
)

# === ENTRY POINT: New albaran uploaded ===
@app.post("/events/blob-created")
async def handle_new_albaran(request: Request):
    events = await request.json()
    for event in events:
        blob_url = event["data"]["url"]
        result = await workflow.run(message=f"Process: {blob_url}")
        # If workflow reached HITL point, it's checkpointed
        # If it completed (no discrepancy), it's done
    return {"status": "ok"}

# === RESUME POINT: Human responded to HITL email ===
@app.post("/events/hitl-response")
async def handle_hitl_response(request: Request):
    data = await request.json()
    workflow_id = data["workflow_id"]
    decision = data["decision"]

    # Resume from checkpoint
    latest = await checkpoint_storage.get_latest(workflow_name=workflow_id)
    if latest:
        result = await workflow.run(
            checkpoint_id=latest.checkpoint_id,
            message=f"Human decision: {decision}",
        )
    return {"status": "resumed"}

# === HEALTH CHECK ===
@app.get("/health")
async def health():
    return {"status": "healthy"}
```

---

## 6. Pattern Comparison for Our Project

| Criterion | Sequential | Handoff | Magentic (Supervisor) | WorkflowBuilder |
|-----------|------------|---------|----------------------|-----------------|
| **Dynamic routing** | ❌ Fixed order | ✅ LLM-decided | ✅ Manager-decided | ✅ Condition-based |
| **HITL support** | ❌ No pause | ⚠️ Handoff to "user" | ✅ Plan review | ✅ Checkpoint + resume |
| **Long waits (24h)** | ❌ | ❌ (in-memory) | ⚠️ With checkpointing | ✅ Cosmos checkpoints |
| **Cross-container** | ❌ In-process | ❌ In-process | ❌ In-process | ❌ In-process |
| **A2A compatible** | Via wrapper | Via wrapper | Via wrapper | Via wrapper |
| **5-8 agents** | ✅ | ✅ | ✅ Best fit | ✅ Most flexible |
| **Complexity** | Low | Medium | Medium-High | High |
| **Token cost** | Low | Medium | High (manager overhead) | Low (no LLM routing) |

### Recommended Pattern for Verdecora

**Primary: `WorkflowBuilder` with `CosmosCheckpointStorage`**
- Gives us conditional routing without LLM overhead
- Native checkpoint/resume for 24h HITL waits
- Can be hosted in ACA with FastAPI
- Deterministic routing (condition functions, not LLM decisions)
- Most cost-effective for a well-defined business process

**Alternative: `MagenticBuilder` (supervisor)**
- If we need the supervisor to handle edge cases dynamically
- Higher token cost but more flexible
- Better for unclear/evolving requirements

**For cross-container scaling (future):** Wrap each agent in A2A and have the supervisor call them via HTTP.

---

## 7. Key Takeaways

1. **MAF v1.0 has 6 orchestration patterns** — more than enough for our 5-8 agent pipeline
2. **All patterns are in-process** by default; use **A2A protocol** for cross-container communication
3. **WorkflowBuilder + CosmosCheckpointStorage** is the best fit for our HITL requirement (24h email waits)
4. **MagenticBuilder** provides true supervisor/dynamic routing if needed
5. **AgentSession serialization** (`to_dict()`/`from_dict()`) allows manual state persistence
6. **Service Bus** is not native but trivially integrable as agent tools
7. **Event-driven invocation** comes from the hosting layer (FastAPI webhooks, Event Grid, Azure Functions triggers)
8. **A2A is the standard** for cross-process agent communication, not custom REST APIs
