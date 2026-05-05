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

### 2026-05-04: MAF v1.0 PoC Complete
- **Branch:** `squad/1-maf-poc` → PR #56
- **What:** Built minimal PoC validating SequentialBuilder + HandoffBuilder patterns
- **3 stub agents:** StubExtractor, StubValidator, StubInventory — each with mock @tool
- **SequentialBuilder:** Confirmed API for linear pipeline (extraction step)
- **HandoffBuilder:** Confirmed API for conditional routing (coincide → Inventory, discrepancia → HITL)
- **HITL:** Validated `handoffs=["StubInventory", "user"]` pattern for human escalation
- **OpenTelemetry:** Console exporter with custom spans wrapping each stage
- **Dry-run mode:** CLI runs without LLM credentials by calling tools directly
- **Key finding:** SequentialBuilder is linear-only; WorkflowBuilder recommended for Sprint 1 deterministic routing
- **Key finding:** HandoffBuilder routing is LLM-dependent (prompt-driven); must test with real model
- **Output:** `src/poc/maf_poc/`, `docs/poc/maf-v1-poc.md`

### 2026-05-05: MAF v1.2.2 Impact Analysis and Upgrade
- **Release:** python-1.2.2 (2026-04-29)
- **Outcome:** Full impact analysis completed; 3 accumulated breaking changes identified between v1.0.0 and v1.2.2.
- **Breaking changes:** HandoffBuilder context fix (v1.0.1 #5136), CosmosCheckpointStorage pickle restriction (v1.1.0 #5200), AgentResponse standardization (v1.2.2 #5301).
- **Key impact:** `_run_workflow()` in pipeline.py, reconciler.py, analyzer.py require AgentResponse output handling.
- **Bishop execution:** Upgraded pyproject.toml to `>=1.2.2,<2.0`, adapted all affected modules, validated with 171 passing tests.
- **PR #86 created:** Commit 61151de — MAF v1.2.2 baseline ready for Sprint 1.
- **Status:** ✅ COMPLETED. System ready for WorkflowBuilder development.

