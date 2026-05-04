from __future__ import annotations

import json

import pytest

from src.agents.prompts import DEFAULT_VALIDATOR_TOOL_NAMES, build_validator_instructions
from src.models import ValidationResult
from src.models.validation import compare_line_values, recommend_validation_action
from tests.fixtures.sample_validations import sample_validation
from tests.unit.agent_test_helpers import StructuredAgentStub

pytestmark = pytest.mark.unit


def test_build_validator_instructions_uses_default_bc_tools() -> None:
    instructions = build_validator_instructions()

    assert "A4 validator agent" in instructions
    assert '"overall_match_pct"' in instructions
    assert DEFAULT_VALIDATOR_TOOL_NAMES[0] in instructions
    assert DEFAULT_VALIDATOR_TOOL_NAMES[1] in instructions
    assert DEFAULT_VALIDATOR_TOOL_NAMES[2] in instructions


def test_validator_prompt_decodes_validation_payload() -> None:
    agent = StructuredAgentStub(response_format=ValidationResult, kwargs={})
    result = sample_validation()

    decoded = agent.decode(json.dumps(result.model_dump(mode="json")))

    assert isinstance(decoded, ValidationResult)
    assert decoded.recommendation == "approve"
    assert decoded.line_comparisons[0].status == "match"


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
