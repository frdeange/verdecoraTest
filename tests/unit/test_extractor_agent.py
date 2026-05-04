from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from src.agents.extractor_agent import create_extractor_agent
from src.config.agents import AgentsConfig
from src.models import AlbaranExtraction, LineItem
from tests.fixtures.sample_albarans import (
    sample_extraction,
    sample_fansa_extraction,
    sample_multi_page_extraction,
    sample_royal_canin_extraction,
)
from tests.unit.agent_test_helpers import StructuredAgentStub, build_structured_agent_stub

pytestmark = pytest.mark.unit


class NamedTool:
    def __init__(self, name: str) -> None:
        self.name = name


@patch("src.agents.extractor_agent.create_structured_agent", side_effect=build_structured_agent_stub)
def test_create_extractor_agent_uses_expected_model_and_prompt(mock_factory: Any) -> None:
    tools = [NamedTool("content_understanding.analyze_document")]
    agent = create_extractor_agent(client=object(), tools=tools)

    assert isinstance(agent, StructuredAgentStub)
    kwargs = mock_factory.call_args.kwargs
    assert kwargs["name"] == "a1-extractor"
    assert kwargs["model"] == "gpt-5"
    assert kwargs["structured_output"] is AlbaranExtraction
    assert kwargs["tools"] == tools
    assert kwargs["handoffs"] == ["a3-coherence"]
    assert "expert document extraction agent" in kwargs["instructions"]
    assert '"confidence_score"' in kwargs["instructions"]
    assert "content_understanding.analyze_document" in kwargs["instructions"]


@patch("src.agents.extractor_agent.create_structured_agent", side_effect=build_structured_agent_stub)
def test_create_extractor_agent_uses_default_tool_names_when_no_tools(mock_factory: Any) -> None:
    create_extractor_agent(client=object())

    instructions = mock_factory.call_args.kwargs["instructions"]
    assert "content_understanding.analyze_document" in instructions
    assert "content_understanding.extract_tables" in instructions


@pytest.mark.parametrize(
    "extraction",
    [
        sample_extraction(),
        sample_fansa_extraction(),
        sample_royal_canin_extraction(),
        sample_multi_page_extraction(),
    ],
)
def test_extractor_agent_decodes_structured_json(extraction: AlbaranExtraction) -> None:
    agent = StructuredAgentStub(structured_output=AlbaranExtraction, kwargs={})

    decoded = agent.decode(json.dumps(extraction.model_dump(mode="json")))

    assert isinstance(decoded, AlbaranExtraction)
    assert decoded.header.supplier_name == extraction.header.supplier_name
    assert decoded.source_pages == extraction.source_pages
    assert decoded.confidence_score == pytest.approx(extraction.confidence_score)


def test_extractor_agent_handles_missing_optional_fields_gracefully() -> None:
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
    agent = StructuredAgentStub(structured_output=AlbaranExtraction, kwargs={})

    decoded = agent.decode(extraction.model_dump(mode="json"))

    assert isinstance(decoded, AlbaranExtraction)
    assert decoded.line_items[0].unit_price is None
    assert decoded.line_items[0].total is None
    assert decoded.extraction_warnings == ["Unit price missing on source document."]


@patch("src.agents.extractor_agent.create_structured_agent", side_effect=build_structured_agent_stub)
def test_extractor_agent_respects_custom_model_config(mock_factory: Any) -> None:
    config = AgentsConfig.model_validate({"models": {"extractor_model": "gpt-4.1"}})

    create_extractor_agent(client=object(), config=config)

    assert mock_factory.call_args.kwargs["model"] == "gpt-4.1"
