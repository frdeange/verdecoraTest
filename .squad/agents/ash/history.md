# Ash — History

## Project Context
- **Project:** Sistema Inteligente de Gestión de Albaranes
- **User:** Kiko de Angel
- **Role:** MAF Specialist
- **Stack:** Microsoft Agent Framework v1.0+ (Python SDK), Semantic Kernel, AutoGen
- **PRD:** prerequisites/pliego-tecnico-albaranes.html

## Learnings

### 2026-05-03: MAF v1.0 Deep Research Complete
- **Package:** `pip install agent-framework` (v1.0.0, GA April 3 2026, Python 3.10+)
- **Heritage:** Unified successor to Semantic Kernel + AutoGen
- **Core classes:** `Agent`, `FoundryChatClient` (in `agent_framework.foundry`), `MCPStreamableHTTPTool`, `AgentSession`
- **Orchestration:** `SequentialBuilder`, `HandoffBuilder`, `ConcurrentBuilder`, `GroupChatBuilder`, `MagenticBuilder` — all in `agent_framework.orchestrations`
- **MCP:** No `McpToolProvider` class. Use `MCPStreamableHTTPTool(name=..., url=...)` for HTTP MCP servers
- **HITL:** `@tool(approval_mode="always_require")` + `result.user_input_requests` pattern
- **Observability:** `configure_otel_providers()` or `configure_azure_monitor()` + `enable_instrumentation()`
- **PRD pseudocode issues found:** Wrong import paths, non-existent classes (`McpToolProvider`, `HandoffWorkflow`), incorrect `FoundryChatClient` constructor. Full corrections documented in `prerequisites/analysis/ash-maf-research.md`
- **Output:** `prerequisites/analysis/ash-maf-research.md`

### 2026-05-04: MAF Multi-Agent Orchestration Patterns Research
- **6 orchestration patterns documented:** Sequential, Handoff, Concurrent, GroupChat, Magentic (Supervisor), WorkflowBuilder (custom graph)
- **All patterns are in-process** — cross-container communication uses A2A protocol (`agent-framework-a2a`)
- **WorkflowBuilder + CosmosCheckpointStorage** = best fit for 24h HITL waits (checkpoint → scale-to-zero → resume)
- **MagenticBuilder** = supervisor pattern with LLM-managed dynamic routing, supports plan review and checkpointing
- **A2A protocol** = standard for cross-process agent communication (HTTP/JSON-RPC, Agent Cards for discovery)
- **AgentSession serialization** (`to_dict()`/`from_dict()`) enables manual state persistence to any store
- **Service Bus** not native to MAF but trivially integrable as agent tools
- **Recommendation:** Use WorkflowBuilder with conditional edges for our deterministic business process; MagenticBuilder as alternative for dynamic edge cases
- **Output:** `prerequisites/analysis/ash-maf-multiagent-patterns.md`
