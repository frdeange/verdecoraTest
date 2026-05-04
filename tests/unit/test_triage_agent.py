from __future__ import annotations

import json
from typing import Any

import pytest

from src.agents.prompts import build_triage_instructions
from src.models import DocumentType, TriageResult
from tests.fixtures.sample_albarans import sample_triage_result
from tests.unit.agent_test_helpers import StructuredAgentStub

pytestmark = pytest.mark.unit


def test_build_triage_instructions_embeds_json_schema() -> None:
    instructions = build_triage_instructions()

    assert "Respond with a JSON object matching this schema" in instructions
    assert '"document_type"' in instructions
    assert '"confidence"' in instructions
    assert "Common German" in instructions


@pytest.mark.parametrize(
    ("payload", "expected_language", "expected_routing"),
    [
        (sample_triage_result(language="es", confidence=0.93).model_dump(mode="json"), "es", "extract"),
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
def test_triage_prompt_output_decodes_supported_languages(
    payload: dict[str, Any], expected_language: str, expected_routing: str
) -> None:
    agent = StructuredAgentStub(response_format=TriageResult, kwargs={})

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
def test_triage_prompt_handles_routing_decisions(
    document_type: DocumentType, confidence: float, routing_decision: str
) -> None:
    agent = StructuredAgentStub(response_format=TriageResult, kwargs={})
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
