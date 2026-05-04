from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from src.agents.triage_agent import _build_triage_instructions, create_triage_agent
from src.config.agents import AgentsConfig
from src.models import DocumentType, TriageResult
from tests.fixtures.sample_albarans import sample_triage_result
from tests.unit.agent_test_helpers import StructuredAgentStub, build_structured_agent_stub

pytestmark = pytest.mark.unit


@patch("src.agents.triage_agent.create_structured_agent", side_effect=build_structured_agent_stub)
def test_create_triage_agent_uses_expected_model_and_prompt(mock_factory: Any) -> None:
    agent = create_triage_agent(client=object())

    assert isinstance(agent, StructuredAgentStub)
    kwargs = mock_factory.call_args.kwargs
    assert kwargs["name"] == "a2-triage"
    assert kwargs["model"] == "gpt-5-mini"
    assert kwargs["structured_output"] is TriageResult
    assert kwargs["handoffs"] == ["a1-extractor", "user"]
    assert "document triage specialist" in kwargs["instructions"]
    assert '"routing_decision"' in kwargs["instructions"]


def test_build_triage_instructions_embeds_json_schema() -> None:
    instructions = _build_triage_instructions()

    assert "Respond with a JSON object matching this schema" in instructions
    assert '"document_type"' in instructions
    assert '"confidence"' in instructions
    assert "Common German" in instructions


@pytest.mark.parametrize(
    ("payload", "expected_language", "expected_routing"),
    [
        (
            sample_triage_result(language="es", confidence=0.93).model_dump(mode="json"),
            "es",
            "extract",
        ),
        (
            sample_triage_result(language="it", supplier_id="FANSA", confidence=0.89).model_dump(mode="json"),
            "it",
            "extract",
        ),
        (
            sample_triage_result(language="de", supplier_id="ROYAL-CANIN", confidence=0.87).model_dump(mode="json"),
            "de",
            "extract",
        ),
    ],
)
def test_triage_agent_decodes_supported_languages(
    payload: dict[str, Any], expected_language: str, expected_routing: str
) -> None:
    agent = StructuredAgentStub(structured_output=TriageResult, kwargs={})

    decoded = agent.decode(json.dumps(payload))

    assert isinstance(decoded, TriageResult)
    assert decoded.language == expected_language
    assert decoded.routing_decision == expected_routing


@pytest.mark.parametrize(
    ("document_type", "confidence", "routing_decision"),
    [
        (DocumentType.ALBARAN, 0.92, "extract"),
        (DocumentType.UNKNOWN, 0.22, "reject"),
        (DocumentType.ALBARAN, 0.41, "manual_review"),
    ],
)
def test_triage_agent_handles_routing_decisions(
    document_type: DocumentType, confidence: float, routing_decision: str
) -> None:
    agent = StructuredAgentStub(structured_output=TriageResult, kwargs={})
    payload = sample_triage_result(
        document_type=document_type,
        confidence=confidence,
        routing_decision=routing_decision,
        reasoning="Damaged scan" if routing_decision == "manual_review" else "Structured payload",
    )

    decoded = agent.decode(payload.model_dump(mode="json"))

    assert isinstance(decoded, TriageResult)
    assert decoded.document_type is document_type
    assert decoded.confidence == pytest.approx(confidence)
    assert decoded.routing_decision == routing_decision


@patch("src.agents.triage_agent.create_structured_agent", side_effect=build_structured_agent_stub)
def test_triage_agent_respects_custom_model_config(mock_factory: Any) -> None:
    config = AgentsConfig.model_validate({"models": {"gpt5_mini_deployment": "triage-local"}})

    create_triage_agent(client=object(), config=config)

    assert mock_factory.call_args.kwargs["model"] == "triage-local"
