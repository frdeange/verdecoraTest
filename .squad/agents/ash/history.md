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
