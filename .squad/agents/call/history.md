# Call — History

## Project Context
- **Project:** Sistema Inteligente de Gestión de Albaranes
- **User:** Kiko de Angel
- **Role:** Foundry Specialist
- **Stack:** Azure AI Foundry Agent Service, Azure OpenAI, Application Insights
- **PRD:** prerequisites/pliego-tecnico-albaranes.html

## Learnings

### 2026-05-03 — Azure AI Foundry Agent Service research
- The **service itself is GA**, but the official docs still mark **hosted agents**, **workflow agents**, and **non-prompt tracing** as **preview**.
- The public data-plane uses **`api-version=v1`**; hosted session APIs are still preview-gated.
- **Prompt/workflow/native agents** have no extra runtime fee beyond model/tool charges; **hosted agents** add managed container compute billing.
- Hosted agents are **container-based**, scale to zero after **15 minutes idle**, and preserve session state for up to **30 days**.
- MCP is production-relevant now: Foundry can connect to **remote public or private MCP endpoints**, with per-agent allow-lists and approval settings.
- Best architecture split for this project: **Foundry for agent runtime**, **Container Apps/Functions for event adapters, webhook processors, and private/custom MCP hosting**.
