# Azure AI Foundry Agent Service Research

Prepared by: Call (Foundry Specialist)  
Date: 2026-05-03

## 1. Foundry Agent Service Current Capabilities

### Current state today
- **Microsoft Foundry Agent Service is generally available as a service in the new Foundry experience**, but the service is **not uniformly GA across every agent type and feature**.
- The clearest current split from official docs is:
  - **Prompt agents**: production-ready / GA surface.
  - **Workflow agents**: **preview**.
  - **Hosted agents**: **preview**.
  - **Tracing**: **GA for prompt agents only**; **workflow, hosted, and custom agent tracing are preview**.
- The public data-plane examples now use **`api-version=v1`** for agent endpoints. Management-plane capability-host examples use **`api-version=2025-06-01`**.

### What the service offers today
From the official docs plus current MCP discovery, the platform currently offers:
- **Persistent, versioned agents** identified by **agent name + version** (not legacy GUID-only agent IDs).
- **Prompt agents** managed entirely by Foundry.
- **Hosted agents** that run **our own container image** on Foundry-managed runtime.
- **Workflow agents** for orchestration (still preview).
- **Conversations and responses** as first-class runtime objects for multi-turn stateful interactions.
- **Built-in tools** plus **remote MCP tools**, search, memory, code interpreter, web search, and toolbox aggregation.
- **Tracing, evaluations, metrics, and Application Insights integration**.
- **Publishing** to stable endpoints and sharing into Teams / Microsoft 365 / Entra Agent Registry.
- **Identity and security** via per-agent Entra identity, RBAC, and private networking.

### Azure Foundry MCP operations discovered today
The current `azure-foundry` MCP surface exposes operations that line up with the above, including:
- `agent_update`, `agent_get`, `agent_delete`, `agent_invoke`
- `agent_definition_schema_get`
- `agent_container_status_get`, `agent_container_control`
- `project_connection_create|get|list|update|delete|list_metadata`
- evaluation and dataset operations
- `model_monitoring_metrics_get`

This is important because it confirms that **agent lifecycle, connection lifecycle, evaluation, and monitoring are already represented as first-class platform operations today**.

### How persistent agents are created and managed
There are two main patterns:
1. **Prompt agents**
   - Create a **named, versioned** agent definition with model + instructions + tools.
   - Runtime state is handled through **conversations** and **responses**.
2. **Hosted agents**
   - Create a hosted agent version that points to a **container image in ACR**.
   - Each hosted agent version declares protocol support (for example `responses` and/or `invocations`).
   - Hosted agents also use **sessions** for persisted sandbox state.

For hosted agents specifically:
- Foundry provisions compute on demand.
- Session state persists across idle periods.
- **Idle timeout is 15 minutes**.
- **Session lifetime is up to 30 days**.
- Files persist via `$HOME` and `/files` endpoints.

### Pricing model
The current official pricing model is:
- **Prompt/workflow/native Foundry agents**: **no additional runtime charge** for the agent runtime itself.
  - You still pay for:
    - **model tokens / inference**
    - **tool usage**
    - **knowledge / connector usage**
    - any separately billed services (for example Logic Apps connectors, Bing grounding, SharePoint, Search, etc.)
- **Code Interpreter**: billed **per session**.
- **File Search**: billed by **vector storage usage**.
- **Hosted agents**: billed by **underlying container compute consumption**:
  - **vCPU-hour**
  - **GiB-memory-hour**
- **Tracing/observability storage costs** follow the connected **Application Insights / Log Analytics** pricing and retention settings.

**Bottom line:** if we stay on prompt agents, the cost center is mostly tokens + tools; if we choose hosted agents, we add a managed container-runtime bill on top.

**Key sources:**
- Agent overview: https://learn.microsoft.com/azure/foundry/agents/overview
- Runtime components: https://learn.microsoft.com/azure/foundry/agents/concepts/runtime-components
- Hosted agents: https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents
- FAQ / pricing: https://learn.microsoft.com/azure/foundry/agents/faq
- Pricing page: https://azure.microsoft.com/en-us/pricing/details/foundry-agent-service/
- GA announcement: https://devblogs.microsoft.com/foundry/foundry-agent-service-ga/

## 2. Agent Hosting & Deployment Model

### Deployment model
There are **two distinct hosting models**:

1. **Prompt agents**
- **API-managed / definition-based**.
- We store instructions, tools, model choice, and configuration in Foundry.
- No customer container is required.

2. **Hosted agents**
- **Container-based**.
- We build and push a container image to **Azure Container Registry**.
- Foundry **pulls the image**, provisions compute, assigns a **dedicated Entra agent identity**, and exposes a dedicated endpoint.
- Foundry manages:
  - hosting
  - scaling
  - session persistence
  - observability
  - lifecycle/versioning

### Protocols and invocation patterns
Hosted agents can expose:
- **Responses** protocol: OpenAI-compatible, best for conversational agents.
- **Invocations** protocol: arbitrary JSON in/out, best for webhooks and event payloads.
- Also documented: **Activity** (Teams/M365) and **A2A** (agent-to-agent).

### External event triggering
**Yes, but mostly indirectly / via HTTP integration patterns rather than first-class event-source bindings.**

What is supported today:
- **Webhook-style triggers** are explicitly supported through the **Invocations** protocol.
- The docs position Invocations for external systems such as **GitHub, Stripe, Jira, etc.**
- The Responses protocol also supports **background execution** (`background: true`) for async agent work once invoked.

What is **not clearly documented as a first-class Foundry feature** today:
- native **Event Grid subscription target** management inside Foundry
- native **Cosmos DB Change Feed binding** inside Foundry

Practical implication:
- If an upstream system can send HTTP directly, a hosted agent using **Invocations** can be the receiver.
- For Azure-native event routing (Event Grid, Service Bus, Change Feed, etc.), the safer production pattern is still:
  - **Event source** -> **Container Apps / Functions / Logic Apps** -> **Foundry agent endpoint**

### Auto-scaling behavior
Official docs describe hosted agents as:
- **provision compute on demand**
- **deprovision after 15 minutes idle**
- effectively **scale to zero** when idle
- restore persisted session state when the session resumes

Docs do **not** publish strict latency SLAs or public p50/p95 runtime numbers.

### Latency characteristics
What we can say confidently today:
- **Warm path** latency depends on model + tools + downstream systems.
- **Cold start latency exists** after idle deprovisioning.
- Foundry explicitly optimizes around **stateful resume** after scale-to-zero, but does not publish hard performance guarantees in the docs I found.
- For event-driven or webhook traffic with bursty idle gaps, we should assume **cold-start penalty after 15 minutes idle**.

**Recommendation:** treat Foundry hosted agents as a managed container runtime with scale-to-zero, not as a low-latency always-hot microservice platform.

**Key sources:**
- Hosted agents: https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents
- Manage hosted agents: https://learn.microsoft.com/azure/foundry/agents/how-to/manage-hosted-agent
- Manage hosted sessions: https://learn.microsoft.com/azure/foundry/agents/how-to/manage-hosted-sessions

## 3. MCP Tool Provider Configuration

### Can Foundry agents use MCP today?
**Yes.** MCP is now a documented first-class tool pattern in Foundry Agent Service.

### How to register MCP servers
Per official docs, MCP registration is done by attaching an **MCP tool** to the agent with fields such as:
- `server_label`
- `server_url`
- `project_connection_id` (optional, for authenticated servers)
- `allowed_tools`
- `require_approval`

This can be done in code or through Foundry tooling / Add Tools catalog patterns.

### Public vs private MCP connectivity
Foundry supports both:
- **Public remote MCP endpoints**
  - usable with **Basic** and **Standard** agent setup
- **Private MCP endpoints**
  - require **Standard Agent Setup + private networking**
  - require a **dedicated MCP subnet**
  - official guidance is to host the private MCP server on **Azure Container Apps** with internal-only ingress

### Can Foundry connect to external MCP servers (BC, custom, etc.)?
**Yes, if they are exposed as remote MCP-compatible endpoints.**

That means:
- **Business Central / BC MCP**: yes, if exposed as a remote MCP server and authenticated appropriately.
- **Custom MCP servers**: yes.
- **Local-only MCP servers**: not directly; they must be hosted remotely (for example on **Azure Functions** or **Azure Container Apps**).

### Tool permissions per agent
Foundry gives us real control here:
- `allowed_tools` = per-agent allow-list of exposed MCP tools
- `require_approval` = approval mode for tool invocation
  - `always`
  - `never`
  - selective per-tool approval policies

This is the current answer to **"tool permissions per agent"**: permissions are effectively enforced at the **agent tool configuration layer**, not as a separate standalone policy object.

### Authentication patterns
Official docs and skill references indicate MCP auth can use:
- API keys / stored secrets through **project connections**
- Microsoft Entra identity
- OAuth / OBO passthrough in supported cases
- unauthenticated access where appropriate

### Toolbox angle
**Foundry Toolboxes (preview)** can aggregate multiple tools behind a single MCP-compatible endpoint. That is useful if we want:
- centralized tool governance
- versioned tool bundles
- one endpoint consumed by multiple agents/runtimes

**Key sources:**
- MCP tool docs: https://learn.microsoft.com/azure/foundry/agents/how-to/tools/model-context-protocol
- Azure Functions MCP integration: https://learn.microsoft.com/azure/azure-functions/functions-mcp-foundry-tools
- Foundry Toolbox docs: linked from MCP docs

## 4. Telemetry & Observability

### How to connect Foundry to Application Insights
Official setup flow:
- Open Foundry project
- Go to **Agents -> Traces**
- **Connect** an existing or new **Application Insights** resource

Alternative path:
- Project details -> Connected resources -> Add connection -> Application Insights

### What telemetry is auto-generated
Once tracing is enabled:
- Foundry automatically stores traces in **Application Insights**.
- Foundry uses **OpenTelemetry semantic conventions**.
- The platform can automatically log server-side traces for:
  - prompt agents
  - hosted agents
  - workflows
- Foundry portal shows out-of-the-box traces for the last **90 days**.

Telemetry documented as available includes:
- latency / duration
- exceptions
- prompt content
- retrieval operations
- tool usage / tool calls / tool results
- token consumption
- response / conversation correlation

### What still needs manual setup
Manual work is still needed for:
- **connecting Application Insights** in the project
- **client-side tracing** from our own code when we want richer telemetry from SDK/framework code paths
- framework-specific instrumentation (LangChain, LangGraph, custom agents, etc.)
- access control on App Insights / Log Analytics (for example **Log Analytics Reader**)
- retention / cost tuning in Azure Monitor

### GA vs preview nuance
Important current nuance from docs:
- **Tracing is GA for prompt agents**.
- **Hosted, workflow, and custom tracing are preview**.

So telemetry exists for all of them, but **the safest production commitment today is strongest on prompt agents**.

### OpenTelemetry / GenAI semantic conventions
**Yes, supported.**

Official docs explicitly say Foundry stores traces in Application Insights using **OpenTelemetry semantic conventions**, including **GenAI semantic conventions**.
They also document multi-agent observability extensions for:
- Foundry
- Microsoft Agent Framework
- LangChain
- LangGraph
- OpenAI Agents SDK

### Operational implication
If observability is a hard production requirement, Foundry already gives us:
- first-party tracing
- App Insights backend
- cross-tool visibility
- evaluation + monitoring alignment

But if we choose **hosted agents**, we should treat telemetry maturity as **usable but preview-labeled** today.

**Key sources:**
- Tracing setup: https://learn.microsoft.com/azure/foundry/observability/how-to/trace-agent-setup
- Tracing overview: https://learn.microsoft.com/azure/foundry/observability/concepts/trace-agent-concept
- Azure Monitor agent view: https://learn.microsoft.com/azure/azure-monitor/app/agents-view

## 5. Foundry vs Container Apps — Architecture Split

### What belongs in Foundry
Foundry is the right home for:
- agent definitions and versions
- prompt agents
- hosted agent runtime (if we accept preview)
- conversations / responses / sessions
- model access and tool orchestration
- agent identities
- tracing / evals / monitoring
- publishing and stable agent endpoints

### What still belongs in Container Apps (or Functions)
Container Apps still makes sense for:
- **event receivers** (Event Grid, webhooks, Service Bus adapters, Change Feed processors)
- **integration adapters** that normalize external payloads before calling Foundry
- **private MCP servers**
- **custom APIs / background processors** that are not themselves the agent runtime
- other edge services we want to own independently of Foundry lifecycle

### Best interpretation of the PRD split
The most sensible split is:
- **Foundry = agent runtime + orchestration + telemetry + identity**
- **Container Apps = integration edge / webhook processors / MCP hosting / event adapters**

So yes: **Container Apps for webhooks/processors, Foundry for agents** is the cleanest architecture.

### Can Foundry handle the full lifecycle alone?
**Sometimes, but not always.**

It can handle most of the lifecycle when:
- the agent is prompt-based
- triggers are user/API driven
- tools are built-in or already remote
- no custom ingress/event-adapter layer is required

It cannot fully replace Container Apps when we need:
- Azure-native event adapters
- custom webhook ingress control
- private MCP hosting
- non-agent microservices
- decoupled integration services with their own lifecycle

### Recommendation for this project
Do **not** duplicate the agent runtime in both places.
- If the runtime is a **Foundry hosted agent**, let Foundry host it.
- Use **Container Apps** only for the surrounding integration surfaces that Foundry does not natively own well.

## 6. Recommendations

1. **Use Foundry as the primary agent platform.**
   - It already owns agent lifecycle, identity, conversations, tools, tracing, evaluation, and publishing.

2. **Prefer prompt agents first if GA/stability is the priority.**
   - Today, prompt agents are the most mature/GA-aligned surface.
   - Hosted agents are powerful, but still preview-labeled in official docs.

3. **Use hosted agents only where custom runtime logic is genuinely required.**
   - Good fit for custom orchestration, webhook-native invocations, custom protocols, or framework-owned code.

4. **Keep Container Apps in the architecture, but narrow the scope.**
   - Use it for event adapters, webhook processors, and private/custom MCP servers.
   - Do not use ACA as a second general-purpose agent runtime if Foundry is already hosting the agent.

5. **Adopt MCP with explicit allow-lists and approval.**
   - For every MCP server, configure `allowed_tools` and `require_approval` conservatively.
   - Prefer remote, trusted MCP endpoints; host custom/private MCP on ACA when needed.

6. **Connect Application Insights on day one.**
   - Make tracing mandatory from the first prototype so we get conversation, tool, latency, and failure visibility early.

7. **Model the event-driven story explicitly.**
   - If upstream systems emit Event Grid or Change Feed events, route them through ACA / Functions / Logic Apps, then invoke Foundry.
   - Do not assume Foundry itself is the event bus.

8. **Architecture decision for the PRD:**
   - Recommended target split:
     - **Foundry:** agent runtime, versions, sessions, tracing, evals, publishing
     - **Container Apps:** event ingress, MCP hosting, integration adapters

## Executive take-away
Foundry Agent Service is mature enough today to be the **platform control plane and runtime plane for agents**, especially for prompt agents. But the docs still draw a clear maturity boundary: **hosted agents and some observability surfaces remain preview**, so the safest architecture is **Foundry for agents, Container Apps for eventing/adapters/MCP hosting**, not Container Apps as a duplicate agent host.