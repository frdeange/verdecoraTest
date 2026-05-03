# Squad Decisions

## Active Decisions

### 2026-05-03: Lenguaje de implementación — Python
**By:** Kiko de Angel
**What:** Todo el proyecto se implementa en Python, salvo la parte de IaC (Bicep). Esto incluye agentes IA, MCP servers custom (si los hubiera), webhooks, procesadores, y tests.
**Why:** Preferencia del usuario. Microsoft Agent Framework v1.0+ tiene SDK principal en Python.

### 2026-05-03: Metodología DevOps estricta
**By:** Kiko de Angel
**What:** Todo trabajo sigue el ciclo obligatorio: Issue → Branch → Dev → Test → Commit → Push → PR → Review → Merge → Close. Sin excepciones. Hicks (DevOps Lead) lo hace cumplir.
**Why:** Directiva del usuario para mantener trazabilidad y calidad en todo el ciclo de vida.

### 2026-05-03: MCP Servers custom — evaluar antes de implementar
**By:** Kiko de Angel
**What:** No dar por hecho que se necesitan MCP servers custom para Blob/Cosmos/DocIntel. El MCP nativo de Azure y BC puede cubrir muchas necesidades. Newt (MCP Analyst) debe evaluar qué se necesita realmente. Para Teams, considerar WorkIQ como alternativa.
**Why:** Simplificar la arquitectura evitando componentes innecesarios.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
