from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from src.agents.validator_agent import compare_line_values, create_validator_agent, recommend_validation_action
from src.config.agents import AgentsConfig
from src.models import ValidationResult
from tests.fixtures.sample_validations import sample_validation
from tests.unit.agent_test_helpers import StructuredAgentStub, build_structured_agent_stub

pytestmark = pytest.mark.unit


class NamedTool:
    def __init__(self, name: str) -> None:
        self.name = name


@patch("src.agents.validator_agent.create_structured_agent", side_effect=build_structured_agent_stub)
def test_create_validator_agent_uses_expected_model_and_prompt(mock_factory: Any) -> None:
    tools = [NamedTool("bc.get_purchase_order_lines")]
    agent = create_validator_agent(client=object(), tools=tools)

    assert isinstance(agent, StructuredAgentStub)
    kwargs = mock_factory.call_args.kwargs
    assert kwargs["name"] == "a4-validator"
    assert kwargs["model"] == "gpt-5-mini"
    assert kwargs["structured_output"] is ValidationResult
    assert kwargs["tools"] == tools
    assert "A4 validator agent" in kwargs["instructions"]
    assert '"overall_match_pct"' in kwargs["instructions"]
    assert "bc.get_purchase_order_lines" in kwargs["instructions"]


@patch("src.agents.validator_agent.create_structured_agent", side_effect=build_structured_agent_stub)
def test_create_validator_agent_uses_default_bc_tools_when_no_tools(mock_factory: Any) -> None:
    create_validator_agent(client=object())

    instructions = mock_factory.call_args.kwargs["instructions"]
    assert "bc.search_purchase_orders" in instructions
    assert "bc.get_purchase_order_lines" in instructions
    assert "bc.search_items" in instructions


def test_validator_agent_decodes_validation_payload() -> None:
    agent = StructuredAgentStub(structured_output=ValidationResult, kwargs={})
    result = sample_validation()

    decoded = agent.decode(json.dumps(result.model_dump(mode="json")))

    assert isinstance(decoded, ValidationResult)
    assert decoded.recommendation == "approve"
    assert decoded.line_comparisons[0].status == "match"


@patch("src.agents.validator_agent.create_structured_agent", side_effect=build_structured_agent_stub)
def test_validator_agent_respects_custom_model_config(mock_factory: Any) -> None:
    config = AgentsConfig.model_validate({"models": {"gpt5_mini_deployment": "validator-local"}})

    create_validator_agent(client=object(), config=config)

    assert mock_factory.call_args.kwargs["model"] == "validator-local"


@pytest.mark.parametrize(
    ("extracted_value", "bc_value", "tolerance_pct", "expected_status"),
    [
        (10, 10, 2.0, "match"),
        (10.1, 10, 2.0, "tolerance"),
        (12, 10, 2.0, "mismatch"),
    ],
)
def test_compare_line_values_handles_match_mismatch_and_tolerance(
    extracted_value: float,
    bc_value: float,
    tolerance_pct: float,
    expected_status: str,
) -> None:
    comparison = compare_line_values(
        line_number=1,
        field="quantity",
        extracted_value=extracted_value,
        bc_value=bc_value,
        tolerance_pct=tolerance_pct,
    )

    assert comparison.status == expected_status


@pytest.mark.parametrize(
    ("overall_match_pct", "expected_recommendation"),
    [
        (0.96, "approve"),
        (0.95, "hitl_review"),
        (0.80, "hitl_review"),
        (0.79, "reject"),
    ],
)
def test_recommend_validation_action_respects_thresholds(
    overall_match_pct: float,
    expected_recommendation: str,
) -> None:
    assert recommend_validation_action(overall_match_pct) == expected_recommendation
