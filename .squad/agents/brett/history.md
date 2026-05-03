# Brett — History

## Project Context
- **Project:** Sistema Inteligente de Gestión de Albaranes
- **User:** Kiko de Angel
- **Role:** Private Network & CI/CD Specialist
- **Stack:** Azure VNet, Private Endpoints, ACA self-hosted runners, Private DNS, NAT Gateway
- **Region:** Sweden Central
- **PRD:** prerequisites/pliego-tecnico-albaranes.html

## Learnings

### 2026-05-03 — Private networking + ACA runners viability
- Researched Microsoft-documented self-hosted GitHub Actions runners on **Azure Container Apps Jobs** for Sweden Central private-network deployment.
- Confirmed the pattern is viable for **private IaC/control-plane deployment**, but **not** for Docker-heavy workflows because ACA Jobs do not support Docker-in-Docker.
- Recommended a phased bootstrap: deploy runner control plane first, then add Private Endpoints + DNS, then disable public access and move all later deployments onto self-hosted runners.
- Recommended two ACA workload-profile environments: one for app workloads and one for runner jobs, plus a dedicated private-endpoint subnet.
- Captured service compatibility/caveats for Cosmos DB, Blob, Key Vault, Azure OpenAI, Document Intelligence, Foundry Agent Service, ACA, and Service Bus in `prerequisites/analysis/brett-private-networking.md`.
