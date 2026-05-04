# Post-MVP agents

## A7 Reconciliation

- **Purpose:** daily reconciliation between posted Business Central purchase receipts and the Cosmos audit trail.
- **Runtime:** Azure Container Apps Job `verdecora-reconciliation-dev` scheduled at `0 6 * * *` (06:00 UTC).
- **Inputs:** Cosmos processing records from the last 24 hours, Business Central posted purchase receipts for the same window.
- **Output:** `ReconciliationReport` with drift items classified as missing in BC, missing in Cosmos, amount mismatch, or status mismatch.
- **Automation guardrails:** safe repost candidates are only proposed as HITL-gated fixes; the job emails a drift summary through ACS Email.

## A8 Learning

- **Purpose:** learn supplier behavior patterns and turn them into conservative reputation updates and feature-flag proposals.
- **Runtime:** Azure Container Apps Job `verdecora-learning-dev` scheduled at `0 4 * * 0` (Sunday 04:00 UTC).
- **Inputs:** seven days of processed albarán history from Cosmos.
- **Output:** `LearningReport` with supplier reputation updates, insights, and optional feature flag proposals.
- **Feedback loop:** supplier reputation is stored through the feature-flags configuration path so triage/validation can consume supplier-specific tolerances and auto-approve eligibility later.
