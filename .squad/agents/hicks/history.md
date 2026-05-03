# Hicks — History

## Project Context
- **Project:** Sistema Inteligente de Gestión de Albaranes
- **User:** Kiko de Angel
- **Role:** DevOps Lead
- **Stack:** GitHub Actions, Python, Bicep CI/CD
- **PRD:** prerequisites/pliego-tecnico-albaranes.html

## Work Log

### 2026-05-03: Initial DevOps Setup
- Created project directory structure (src/, tests/, infra/, docs/, .github/workflows/)
- Created placeholder README.md files for all key directories
- Created initial CI/CD workflow (.github/workflows/ci.yml) with:
  - Python 3.12+ support
  - Linting (flake8) and type checking (mypy)
  - Unit and integration test execution
  - Code coverage reporting
- Attempted to create GitHub labels via API (frdeange/verdecoraTest repo) but encountered permissions limitation (pull-only access). Labels must be created by a team member with admin/write access.

**Note:** GitHub label creation blocked by permissions. Repo owner or admin must run:
```bash
gh label create "squad" --color "0078d4" --description "Untriaged squad work" --force
# ... (and all other labels from task spec)
```

## Learnings

- Repository accessed with pull-only permissions; write operations require admin/maintain role
- Directory structure follows squad best practices: agents, services, models, config separation
- CI/CD pipeline supports Python 3.12+ with coverage tracking
