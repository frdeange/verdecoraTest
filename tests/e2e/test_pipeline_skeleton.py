from __future__ import annotations

from typing import Any

import pytest


@pytest.mark.e2e
def test_full_pipeline_skeleton(full_pipeline_test_skeleton: dict[str, Any]) -> None:
    assert full_pipeline_test_skeleton["name"] == "albaran-to-business-central"
    assert "agent-a5-inventory" in full_pipeline_test_skeleton["stages"]
    assert "inventariado" in full_pipeline_test_skeleton["expected_terminal_states"]
