from __future__ import annotations

import json

import pytest

from src.agents.inventory_agent import build_posting_failure_result, should_process_inventory
from src.agents.prompts import DEFAULT_INVENTORY_TOOL_NAMES, build_inventory_instructions
from src.models import PostingResult
from tests.fixtures.sample_validations import sample_posting_result, sample_validation
from tests.unit.agent_test_helpers import StructuredAgentStub

pytestmark = pytest.mark.unit


def test_build_inventory_instructions_uses_default_bc_tools() -> None:
    instructions = build_inventory_instructions()

    assert "A5 inventory posting agent" in instructions
    assert '"posted_lines"' in instructions
    assert DEFAULT_INVENTORY_TOOL_NAMES[0] in instructions
    assert DEFAULT_INVENTORY_TOOL_NAMES[1] in instructions


def test_inventory_prompt_decodes_posting_result_payload() -> None:
    agent = StructuredAgentStub(response_format=PostingResult, kwargs={})
    result = sample_posting_result()

    decoded = agent.decode(json.dumps(result.model_dump(mode="json")))

    assert isinstance(decoded, PostingResult)
    assert decoded.success is True
    assert decoded.receipt_number == "RCPT-2026-0012"


def test_inventory_agent_only_processes_approved_validations() -> None:
    assert should_process_inventory(sample_validation(overall_match_pct=0.98, recommendation="approve")) is True
    assert should_process_inventory(sample_validation(overall_match_pct=0.9, recommendation="hitl_review")) is False
    assert should_process_inventory(sample_validation(overall_match_pct=0.7, recommendation="reject")) is False


def test_inventory_agent_returns_failure_payload_on_bc_posting_error() -> None:
    result = build_posting_failure_result(RuntimeError("Business Central posting failed"), receipt_number="TEMP-001")

    assert result.success is False
    assert result.receipt_number == "TEMP-001"
    assert result.posted_lines == 0
    assert result.errors == ["Business Central posting failed"]
