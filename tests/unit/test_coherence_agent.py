from __future__ import annotations

import json

import pytest

from src.agents.prompts import DEFAULT_COHERENCE_TOOL_NAMES, build_coherence_instructions
from src.models import CoherenceCheckResult
from tests.fixtures.sample_albarans import sample_coherence_result
from tests.unit.agent_test_helpers import StructuredAgentStub

pytestmark = pytest.mark.unit


def test_build_coherence_instructions_uses_default_bc_tools() -> None:
    instructions = build_coherence_instructions()

    assert "data coherence specialist" in instructions
    assert '"overall_confidence"' in instructions
    assert DEFAULT_COHERENCE_TOOL_NAMES[0] in instructions
    assert DEFAULT_COHERENCE_TOOL_NAMES[1] in instructions
    assert DEFAULT_COHERENCE_TOOL_NAMES[2] in instructions


def test_coherence_prompt_accepts_coherent_document() -> None:
    agent = StructuredAgentStub(response_format=CoherenceCheckResult, kwargs={})
    result = sample_coherence_result(is_coherent=True, overall_confidence=0.94, bc_match_found=True)

    decoded = agent.decode(json.dumps(result.model_dump(mode="json")))

    assert isinstance(decoded, CoherenceCheckResult)
    assert decoded.is_coherent is True
    assert decoded.bc_match_found is True
    assert decoded.line_item_issues == []


def test_coherence_prompt_flags_total_mismatch() -> None:
    agent = StructuredAgentStub(response_format=CoherenceCheckResult, kwargs={})
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


def test_coherence_prompt_tracks_bc_matches_and_tolerance_checks() -> None:
    agent = StructuredAgentStub(response_format=CoherenceCheckResult, kwargs={})
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
