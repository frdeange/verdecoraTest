from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from src.agents.inventory_agent import (
    build_posting_failure_result,
    create_inventory_agent,
    should_process_inventory,
)
from src.config.agents import AgentsConfig
from src.models import PostingResult
from tests.fixtures.sample_validations import sample_posting_result, sample_validation
from tests.unit.agent_test_helpers import StructuredAgentStub, build_structured_agent_stub

pytestmark = pytest.mark.unit


class NamedTool:
    def __init__(self, name: str) -> None:
        self.name = name


@patch("src.agents.inventory_agent.create_structured_agent", side_effect=build_structured_agent_stub)
def test_create_inventory_agent_uses_expected_model_and_prompt(mock_factory: Any) -> None:
    tools = [NamedTool("bc.post_purchase_receipt_lines")]
    agent = create_inventory_agent(client=object(), tools=tools)

    assert isinstance(agent, StructuredAgentStub)
    kwargs = mock_factory.call_args.kwargs
    assert kwargs["name"] == "a5-inventory"
    assert kwargs["model"] == "gpt-5-mini"
    assert kwargs["structured_output"] is PostingResult
    assert kwargs["tools"] == tools
    assert "A5 inventory posting agent" in kwargs["instructions"]
    assert '"posted_lines"' in kwargs["instructions"]
    assert "bc.post_purchase_receipt_lines" in kwargs["instructions"]


@patch("src.agents.inventory_agent.create_structured_agent", side_effect=build_structured_agent_stub)
def test_create_inventory_agent_uses_default_bc_tools_when_no_tools(mock_factory: Any) -> None:
    create_inventory_agent(client=object())

    instructions = mock_factory.call_args.kwargs["instructions"]
    assert "bc.create_purchase_receipt" in instructions
    assert "bc.post_purchase_receipt_lines" in instructions


def test_inventory_agent_decodes_posting_result_payload() -> None:
    agent = StructuredAgentStub(structured_output=PostingResult, kwargs={})
    result = sample_posting_result()

    decoded = agent.decode(json.dumps(result.model_dump(mode="json")))

    assert isinstance(decoded, PostingResult)
    assert decoded.success is True
    assert decoded.receipt_number == "RCPT-2026-0012"


@patch("src.agents.inventory_agent.create_structured_agent", side_effect=build_structured_agent_stub)
def test_inventory_agent_respects_custom_model_config(mock_factory: Any) -> None:
    config = AgentsConfig.model_validate({"models": {"gpt5_mini_deployment": "inventory-local"}})

    create_inventory_agent(client=object(), config=config)

    assert mock_factory.call_args.kwargs["model"] == "inventory-local"


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
