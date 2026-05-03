# Brett — runners bootstrap decisions

**Date:** 2026-05-04  
**Issue:** #4 — VNet + self-hosted runners bootstrap

## Decisions captured

1. **Use ACA Jobs, not ACA Apps, for GitHub Actions runners.**
   - Rationale: the runner pool is event-driven and matches the `github-runner` KEDA scaler model.

2. **Use a dedicated internal ACA managed environment on `snet-runners`.**
   - Rationale: isolates CI/CD runner blast radius from the application ACA environment while satisfying the ADR private-network requirement.

3. **Back the runner PAT with Key Vault and a user-assigned managed identity.**
   - Rationale: avoids hard-coding the scaler secret in Bicep and keeps the bootstrap authentication path compatible with later hardening.

4. **Keep Key Vault temporarily reachable during Phase 0 only.**
   - Rationale: the runner job must resolve the PAT before private endpoints/private DNS are in place; the bootstrap guide explicitly requires removing this exception after cutover.

5. **Bootstrap verification uses a manual ACA job start plus the GitHub runners API.**
   - Rationale: this gives a deterministic runner-registration check before the team moves all later deploys to the self-hosted runner pool.

6. **Treat ACA runners as private IaC/control-plane workers only.**
   - Rationale: ACA jobs do not support Docker-in-Docker, so Docker-heavy builds remain out of scope for this runner pool.
