# Newt — History

## Project Context
- **Project:** Sistema Inteligente de Gestión de Albaranes
- **User:** Kiko de Angel
- **Role:** MCP Analyst
- **Stack:** MCP (Model Context Protocol), Azure MCP, BC MCP native, Python
- **PRD:** prerequisites/pliego-tecnico-albaranes.html

## Learnings

- Business Central now has a native MCP server at `https://mcp.businesscentral.dynamics.com`; read access is available by default and write access is enabled through MCP configuration on API pages.
- BC MCP is a strong fit for read scenarios (purchase orders, lines, items, vendors), but warehouse receipt / inventory posting likely needs a small BC API extension exposed through the native BC MCP server rather than a separate custom MCP server.
- In this environment, native Azure MCP covers Blob Storage and Cosmos DB only partially for the PRD: Blob coverage is metadata-oriented and Cosmos coverage is query-oriented; neither fully proves the PRD's write/download path.
- WorkIQ is useful for M365 information retrieval but not for Teams Adaptive Cards, `Action.Submit`, or HITL approval orchestration.
