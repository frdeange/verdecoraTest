from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from src.agents.pipeline import AlbaranPipeline, PipelineDocumentInput, PipelineRunResult
from src.config.agents import AgentsConfig
from src.models import DocumentType
from tests.fixtures.sample_albarans import (
    sample_coherence_result,
    sample_extraction,
    sample_posting_result,
    sample_triage_result,
    sample_validation_result,
)
from tests.unit.agent_test_helpers import FakeAsyncStream, FakeEvent, FakeWorkflow, WorkflowResult


class _AgentMessage:
    def __init__(self, content: str, author_name: str = "agent") -> None:
        self.content = content
        self.author_name = author_name


class _AgentResponse:
    def __init__(self, *, text: str | None = None, messages: list[_AgentMessage] | None = None) -> None:
        self.text = text
        self.messages = messages or []

pytestmark = pytest.mark.unit


def _named_agents() -> dict[str, Any]:
    return {
        "triage": SimpleNamespace(name="triage"),
        "extractor": SimpleNamespace(name="extractor"),
        "coherence": SimpleNamespace(name="coherence"),
        "validator": SimpleNamespace(name="validator"),
        "inventory": SimpleNamespace(name="inventory"),
        "communication": SimpleNamespace(name="communication"),
    }


def _patch_sequential_builder(workflows: dict[str, FakeWorkflow]):
    def _builder(*, participants: list[Any]) -> Any:
        key = ">".join(getattr(participant, "name", str(participant)).casefold() for participant in participants)
        return SimpleNamespace(build=lambda: workflows[key])

    return _builder


def test_pipeline_creation_with_all_agents() -> None:
    pipeline = AlbaranPipeline(agents=_named_agents())

    assert set(pipeline.agents) == {"triage", "extractor", "coherence", "validator", "inventory", "communication"}


@pytest.mark.asyncio
async def test_run_workflow_uses_agent_response_text_from_stream() -> None:
    pipeline = AlbaranPipeline(agents=_named_agents())
    workflow = FakeWorkflow(
        FakeAsyncStream([FakeEvent(_AgentResponse(text='{"status":"ok"}', messages=[_AgentMessage('ignored')]))])
    )

    result = await pipeline._run_workflow(workflow, {"payload": True})

    assert result == '{"status":"ok"}'


@pytest.mark.asyncio
async def test_run_workflow_falls_back_to_agent_response_messages() -> None:
    pipeline = AlbaranPipeline(agents=_named_agents())
    workflow = FakeWorkflow(FakeAsyncStream([FakeEvent(_AgentResponse(messages=[_AgentMessage('{"status":"ok"}')]))]))

    result = await pipeline._run_workflow(workflow, {"payload": True})

    assert result == '{"status":"ok"}'


@pytest.mark.asyncio
async def test_pipeline_run_with_mocked_agents() -> None:
    triage_result = sample_triage_result()
    extraction_result = sample_extraction()
    coherence_result = sample_coherence_result()
    validation_result = sample_validation_result()
    posting_result = sample_posting_result()
    workflows = {
        "triage": FakeWorkflow(
            FakeAsyncStream([FakeEvent({"ignored": True}), FakeEvent(triage_result.model_dump(mode="json"))])
        ),
        "extractor": FakeWorkflow(WorkflowResult(extraction_result.model_dump_json())),
        "coherence": FakeWorkflow(coherence_result.model_dump_json()),
        "validator": FakeWorkflow(validation_result.model_dump(mode="json")),
        "inventory": FakeWorkflow(posting_result.model_dump_json()),
    }
    pipeline = AlbaranPipeline(agents=_named_agents())
    input_data = PipelineDocumentInput(
        document_reference="https://storage/account/albaran.pdf",
        raw_text="ALBARAN DE ENTREGA",
        ocr_payload={"pages": [{"pageNumber": 1}]},
    )

    with patch("src.agents.pipeline.SequentialBuilder", side_effect=_patch_sequential_builder(workflows)):
        result = await pipeline.run(input_data)

    assert isinstance(result, PipelineRunResult)
    assert result.triage == triage_result
    assert result.extraction == extraction_result
    assert result.coherence == coherence_result
    assert result.validation == validation_result
    assert result.inventory == posting_result
    assert result.routing_decision == "posted"
    assert workflows["triage"].payloads == ["ALBARAN DE ENTREGA"]
    assert workflows["extractor"].payloads == [{"pages": [{"pageNumber": 1}]}]
    assert workflows["coherence"].payloads == [extraction_result.model_dump(mode="json")]
    assert workflows["validator"].payloads == [
        {
            "extraction": extraction_result.model_dump(mode="json"),
            "coherence": coherence_result.model_dump(mode="json"),
        }
    ]
    assert workflows["inventory"].payloads == [
        {
            "validation": validation_result.model_dump(mode="json"),
            "extraction": extraction_result.model_dump(mode="json"),
        }
    ]


@pytest.mark.asyncio
async def test_pipeline_propagates_agent_failures() -> None:
    workflows = {
        "triage": FakeWorkflow(RuntimeError("triage failed")),
    }
    pipeline = AlbaranPipeline(agents=_named_agents())

    with (
        patch("src.agents.pipeline.SequentialBuilder", side_effect=_patch_sequential_builder(workflows)),
        pytest.raises(RuntimeError, match="triage failed"),
    ):
        await pipeline.run(PipelineDocumentInput(document_reference="https://storage/account/albaran.pdf"))


@pytest.mark.asyncio
async def test_pipeline_skip_triage_flag_works() -> None:
    config = AgentsConfig.model_validate(
        {
            "skip_triage_suppliers": ["ROYAL CANIN"],
            "thresholds": {"low_value_coherence_threshold": 10.0},
        }
    )
    extraction_result = sample_extraction(supplier_name="Royal Canin", confidence_score=0.82)
    coherence_result = sample_coherence_result(is_coherent=True)
    validation_result = sample_validation_result()
    posting_result = sample_posting_result()
    workflows = {
        "extractor": FakeWorkflow(extraction_result.model_dump(mode="json")),
        "coherence": FakeWorkflow(coherence_result.model_dump(mode="json")),
        "validator": FakeWorkflow(validation_result.model_dump(mode="json")),
        "inventory": FakeWorkflow(posting_result.model_dump(mode="json")),
    }
    pipeline = AlbaranPipeline(config=config, agents=_named_agents())

    with patch("src.agents.pipeline.SequentialBuilder", side_effect=_patch_sequential_builder(workflows)):
        result = await pipeline.run(
            PipelineDocumentInput(
                document_reference="https://storage/account/albaran.pdf",
                supplier_hint="royal canin",
                total_amount=200.0,
            )
        )

    assert result.triage is None
    assert result.extraction == extraction_result
    assert result.coherence == coherence_result
    assert result.validation == validation_result
    assert result.inventory == posting_result
    assert result.skipped_steps == ["triage"]


@pytest.mark.asyncio
async def test_pipeline_stops_after_non_extract_triage_result() -> None:
    rejected_triage = sample_triage_result(
        document_type=DocumentType.UNKNOWN,
        confidence=0.12,
        routing_decision="reject",
        reasoning="Unrelated marketing brochure.",
    )
    workflows = {"triage": FakeWorkflow(rejected_triage.model_dump(mode="json"))}
    pipeline = AlbaranPipeline(agents=_named_agents())

    with patch("src.agents.pipeline.SequentialBuilder", side_effect=_patch_sequential_builder(workflows)):
        result = await pipeline.run({"document_reference": "https://storage/account/flyer.pdf"})

    assert result.triage == rejected_triage
    assert result.extraction is None
    assert result.coherence is None
    assert result.validation is None
    assert result.inventory is None
    assert result.routing_decision == "reject"
    assert result.skipped_steps == ["extractor", "coherence", "validation", "inventory"]


@pytest.mark.asyncio
async def test_pipeline_routes_hitl_review_when_validation_requires_manual_review() -> None:
    extraction_result = sample_extraction()
    coherence_result = sample_coherence_result()
    validation_result = sample_validation_result(
        is_valid=False,
        overall_match_pct=0.9,
        recommendation="hitl_review",
        discrepancies=["Line 2 description needs review."],
    )
    workflows = {
        "triage": FakeWorkflow(sample_triage_result().model_dump(mode="json")),
        "extractor": FakeWorkflow(extraction_result.model_dump(mode="json")),
        "coherence": FakeWorkflow(coherence_result.model_dump(mode="json")),
        "validator": FakeWorkflow(validation_result.model_dump(mode="json")),
    }
    pipeline = AlbaranPipeline(agents=_named_agents())

    with patch("src.agents.pipeline.SequentialBuilder", side_effect=_patch_sequential_builder(workflows)):
        result = await pipeline.run(PipelineDocumentInput(document_reference="https://storage/account/albaran.pdf"))

    assert result.routing_decision == "hitl_review"
    assert result.inventory is None
    assert result.skipped_steps == ["inventory"]
