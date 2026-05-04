from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from src.agents.coherence_agent import create_coherence_agent
from src.config.agents import AgentsConfig
from src.models import CoherenceCheckResult
from tests.fixtures.sample_albarans import sample_coherence_result
from tests.unit.agent_test_helpers import StructuredAgentStub, build_structured_agent_stub

pytestmark = pytest.mark.unit


class NamedTool:
    def __init__(self, name: str) -> None:
        self.name = name


@patch("src.agents.coherence_agent.create_structured_agent", side_effect=build_structured_agent_stub)
def test_create_coherence_agent_uses_expected_model_and_prompt(mock_factory: Any) -> None:
    tools = [NamedTool("bc.search_purchase_orders")]
    agent = create_coherence_agent(client=object(), tools=tools)

    assert isinstance(agent, StructuredAgentStub)
    kwargs = mock_factory.call_args.kwargs
    assert kwargs["name"] == "a3-coherence"
    assert kwargs["model"] == "gpt-5-mini"
    assert kwargs["structured_output"] is CoherenceCheckResult
    assert kwargs["tools"] == tools
    assert "data coherence specialist" in kwargs["instructions"]
    assert '"overall_confidence"' in kwargs["instructions"]
    assert "bc.search_purchase_orders" in kwargs["instructions"]


@patch("src.agents.coherence_agent.create_structured_agent", side_effect=build_structured_agent_stub)
def test_create_coherence_agent_uses_default_bc_tools_when_no_tools(mock_factory: Any) -> None:
    create_coherence_agent(client=object())

    instructions = mock_factory.call_args.kwargs["instructions"]
    assert "bc.search_vendors" in instructions
    assert "bc.search_purchase_orders" in instructions
    assert "bc.search_items" in instructions


def test_coherence_agent_accepts_coherent_document() -> None:
    agent = StructuredAgentStub(structured_output=CoherenceCheckResult, kwargs={})
    result = sample_coherence_result(is_coherent=True, overall_confidence=0.94, bc_match_found=True)

    decoded = agent.decode(json.dumps(result.model_dump(mode="json")))

    assert isinstance(decoded, CoherenceCheckResult)
    assert decoded.is_coherent is True
    assert decoded.bc_match_found is True
    assert decoded.line_item_issues == []


def test_coherence_agent_flags_total_mismatch() -> None:
    agent = StructuredAgentStub(structured_output=CoherenceCheckResult, kwargs={})
    result = sample_coherence_result(
        is_coherent=False,
        overall_confidence=0.38,
        line_item_issues=["Document total does not match line item sum."],
        bc_match_found=False,
        matched_po_number=None,
    )

    decoded = agent.decode(result.model_dump(mode="json"))

    assert isinstance(decoded, CoherenceCheckResult)
    assert decoded.is_coherent is False
    assert decoded.line_item_issues == ["Document total does not match line item sum."]
    assert decoded.bc_match_found is False


def test_coherence_agent_tracks_bc_matches_and_tolerance_checks() -> None:
    agent = StructuredAgentStub(structured_output=CoherenceCheckResult, kwargs={})
    result = sample_coherence_result(
        is_coherent=True,
        overall_confidence=0.9,
        line_item_issues=[],
        bc_match_found=True,
        matched_po_number="PO-2026-0456",
        suggested_corrections={"line_2_total": "Adjusted within 2% tolerance."},
    )

    decoded = agent.decode(result.model_dump(mode="json"))

    assert isinstance(decoded, CoherenceCheckResult)
    assert decoded.matched_po_number == "PO-2026-0456"
    assert decoded.suggested_corrections["line_2_total"] == "Adjusted within 2% tolerance."


@patch("src.agents.coherence_agent.create_structured_agent", side_effect=build_structured_agent_stub)
def test_coherence_agent_respects_custom_model_config(mock_factory: Any) -> None:
    config = AgentsConfig.model_validate({"models": {"gpt5_mini_deployment": "coherence-local"}})

    create_coherence_agent(client=object(), config=config)

    assert mock_factory.call_args.kwargs["model"] == "coherence-local"
