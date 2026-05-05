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

### 2026-05-03: Full project backlog authored (50 issues, Sprints 0-4 + Post-MVP)
- Authored complete idempotent script `.squad/scripts/create-backlog.ps1` with 50 `gh issue create` calls covering Sprint 0 (9), Sprint 1 (11), Sprint 2 (9), Sprint 3 (9), Sprint 4 (10), Post-MVP (2).
- Authored `.squad/scripts/create-labels.ps1` with full taxonomy: 11 squad labels, 4 priority, 5 phase, 9 type labels.
- **Blocker hit:** Copilot CLI auth is EMU account `frdeange_microsoft` with pull-only on `frdeange/verdecoraTest`. GitHub responded: `Unauthorized: As an Enterprise Managed User, you cannot access this content (createIssue)`. Issue creation must be executed by Kiko (or any user with write access).
- Spec + run instructions captured in `.squad/decisions/inbox/hicks-backlog-created.md`.
- Once script runs, `.squad/decisions/inbox/hicks-issue-map.json` will hold the `key -> #issue` mapping for dependency wiring in subsequent automation.

## Learnings
- EMU GitHub accounts cannot write to non-enterprise personal repos even with `repo` token scope; must hand off to a non-EMU user for create operations.
- Squad workflow benefits from a deterministic `key -> issue#` map persisted to disk so dependent agents can reference issues without re-querying GitHub.
- Reworks for rejected stacked PRs are safest in an isolated worktree from `origin/master` so unrelated local changes and lockout branches stay untouched.
- The Upload Web store detector should consume the canonical JSON catalog via `src.shared.stores.loader.load_stores()` and keep the heuristic logic free of hardcoded store lists.
