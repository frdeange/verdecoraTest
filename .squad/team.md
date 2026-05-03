# Squad Team

> Sistema Inteligente de Gestión de Albaranes con Agentes de IA

## Coordinator

| Name | Role | Notes |
|------|------|-------|
| Squad | Coordinator | Routes work, enforces handoffs and reviewer gates. |

## Members

| Name | Role | Charter | Status |
|------|------|---------|--------|
| Ripley | Lead Architect | `.squad/agents/ripley/charter.md` | 🏗️ Active |
| Bishop | AI Agent Developer | `.squad/agents/bishop/charter.md` | 🤖 Active |
| Hicks | DevOps Lead | `.squad/agents/hicks/charter.md` | ⚙️ Active |
| Dallas | Azure Cloud Engineer | `.squad/agents/dallas/charter.md` | ☁️ Active |
| Parker | Backend Developer | `.squad/agents/parker/charter.md` | 🔧 Active |
| Lambert | Security Engineer | `.squad/agents/lambert/charter.md` | 🔒 Active |
| Vasquez | QA Engineer | `.squad/agents/vasquez/charter.md` | 🧪 Active |
| Burke | BC/Dynamics Specialist | `.squad/agents/burke/charter.md` | 📊 Active |
| Hudson | Technical Writer | `.squad/agents/hudson/charter.md` | 📝 Active |
| Ash | MAF Specialist | `.squad/agents/ash/charter.md` | 🔬 Active |
| Newt | MCP Analyst | `.squad/agents/newt/charter.md` | 🔌 Active |
| Call | Foundry Specialist | `.squad/agents/call/charter.md` | 🧠 Active |
| Brett | Private Network & CI/CD Specialist | `.squad/agents/brett/charter.md` | 🔐 Active |
| Scribe | Scribe | `.squad/agents/scribe/charter.md` | 📋 Active |
| Ralph | Work Monitor | `.squad/agents/ralph/charter.md` | 🔄 Active |

## Project Context

- **Project:** Sistema Inteligente de Gestión de Albaranes
- **User:** Kiko de Angel
- **Language:** Python (salvo IaC/Bicep)
- **Stack:** Microsoft Agent Framework v1.0+, Azure AI Foundry Agent Service, Azure Container Apps, Cosmos DB, Blob Storage, Event Grid, Document Intelligence, Business Central (MCP nativo), Teams (HITL)
- **Created:** 2026-05-03
- **PRD:** `prerequisites/pliego-tecnico-albaranes.html`

## DevOps Methodology — STRICT

**Every piece of work MUST follow this cycle. No exceptions.**

1. 📋 **Issue** — Create GitHub Issue with labels and emoji before any work starts
2. 🌿 **Branch** — Create `squad/{issue-number}-{slug}` from `main`
3. 💻 **Develop** — Code changes on the branch
4. 🧪 **Test** — Write and run tests. All must pass.
5. 📝 **Commit** — Reference issue: `feat: description (#N)` or `fix: description (#N)`
6. 🚀 **Push** — Push branch to remote
7. 🔀 **PR** — Create PR via `gh pr create`, reference issue with `Closes #N`
8. 👀 **Review** — Ripley (Lead) reviews. Must be approved.
9. ✅ **CI** — All CI checks must pass
10. 🔗 **Merge** — Merge PR
11. 🏁 **Close** — Issue auto-closed by PR merge

**Violations:** Hicks (DevOps Lead) enforces. Work without an issue is rejected.
