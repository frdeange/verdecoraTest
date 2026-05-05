# Bishop — MAF v1.2.2 upgrade compatibility

- **Date:** 2026-05-05
- **Decision:** Standardize new MAF SDK usage on `agent_framework.Agent` + `default_options={"response_format": Model}` and import orchestration builders from `agent_framework.orchestrations`.
- **Why:** After upgrading to MAF v1.2.2, `ChatAgent` is no longer exported from the top-level package and structured output configuration is expected in `default_options`, not `response_format=`. The workflow event stream also returns `AgentResponse`, so terminal output handling must normalize `.text` / `.messages` consistently.
- **Impact:** New agent code and future upgrades should follow this constructor/import pattern to stay compatible with MAF v1.2.2+ and avoid test collection failures.
