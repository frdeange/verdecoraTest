from __future__ import annotations

import json

import pytest

from src.agents.prompts import DEFAULT_EXTRACTOR_TOOL_NAMES, build_extractor_instructions
from src.models import AlbaranExtraction, LineItem
from tests.fixtures.sample_albarans import (
    sample_extraction,
    sample_fansa_extraction,
    sample_multi_page_extraction,
    sample_royal_canin_extraction,
)
from tests.unit.agent_test_helpers import StructuredAgentStub

pytestmark = pytest.mark.unit


def test_build_extractor_instructions_uses_default_tool_names() -> None:
    instructions = build_extractor_instructions()

    assert "expert document extraction agent" in instructions
    assert '"confidence_score"' in instructions
    assert DEFAULT_EXTRACTOR_TOOL_NAMES[0] in instructions
    assert DEFAULT_EXTRACTOR_TOOL_NAMES[1] in instructions


@pytest.mark.parametrize(
    "extraction",
    [
        sample_extraction(),
        sample_fansa_extraction(),
        sample_royal_canin_extraction(),
        sample_multi_page_extraction(),
    ],
)
def test_extractor_prompt_decodes_structured_json(extraction: AlbaranExtraction) -> None:
    agent = StructuredAgentStub(response_format=AlbaranExtraction, kwargs={})

    decoded = agent.decode(json.dumps(extraction.model_dump(mode="json")))

    assert isinstance(decoded, AlbaranExtraction)
    assert decoded.header.supplier_name == extraction.header.supplier_name
    assert decoded.source_pages == extraction.source_pages
    assert decoded.confidence_score == pytest.approx(extraction.confidence_score)


def test_extractor_prompt_handles_missing_optional_fields_gracefully() -> None:
    incomplete_line = LineItem(
        line_number=1,
        description="Maceta cerámica 20cm",
        quantity=3,
        unit_price=None,
        total=None,
    )
    extraction = sample_extraction(
        line_items=[incomplete_line],
        confidence_score=0.74,
        extraction_warnings=["Unit price missing on source document."],
    )
    agent = StructuredAgentStub(response_format=AlbaranExtraction, kwargs={})

    decoded = agent.decode(extraction.model_dump(mode="json"))

    assert isinstance(decoded, AlbaranExtraction)
    assert decoded.line_items[0].unit_price is None
    assert decoded.line_items[0].total is None
    assert decoded.extraction_warnings == ["Unit price missing on source document."]
