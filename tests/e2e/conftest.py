from __future__ import annotations

import os
from typing import Any

import pytest

pytestmark = pytest.mark.e2e


def _e2e_enabled() -> bool:
    return os.getenv("RUN_E2E_PIPELINE", "").lower() in {"1", "true", "yes", "on"}


@pytest.fixture(autouse=True)
def skip_when_e2e_services_unavailable() -> None:
    if not _e2e_enabled():
        pytest.skip(
            "E2E services unavailable. Set RUN_E2E_PIPELINE=1 to enable the pipeline skeleton."
        )


@pytest.fixture(scope="session")
def full_pipeline_test_skeleton(
    sample_albaran_data: dict[str, object], sample_po_data: dict[str, object]
) -> dict[str, Any]:
    return {
        "name": "albaran-to-business-central",
        "stages": [
            "blob-created-event",
            "flow-0-dedup",
            "agent-a1-extraction",
            "agent-a2-triage",
            "agent-a3-coherence",
            "agent-a4-validator",
            "agent-a5-inventory",
            "acs-hitl-notification",
        ],
        "inputs": {
            "blob_path": sample_albaran_data["blob_path"],
            "albaran_id": sample_albaran_data["id"],
            "purchase_order": sample_po_data["number"],
        },
        "expected_terminal_states": ["inventariado", "rechazado", "escalado"],
    }
