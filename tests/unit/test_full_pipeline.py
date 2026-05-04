from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from src.agents.pipeline import AlbaranPipeline, PipelineDocumentInput
from src.models import DocumentType
from tests.fixtures.sample_albarans import sample_coherence_result, sample_extraction, sample_triage_result
from tests.fixtures.sample_validations import sample_posting_result, sample_validation
from tests.unit.agent_test_helpers import FakeAsyncStream, FakeEvent, FakeWorkflow

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


def build_pipeline() -> AlbaranPipeline:
    return AlbaranPipeline(agents=_named_agents())


@pytest.mark.asyncio
async def test_full_pipeline_happy_path_posts_inventory() -> None:
    triage_result = sample_triage_result()
    extraction_result = sample_extraction()
    coherence_result = sample_coherence_result()
    validation_result = sample_validation(overall_match_pct=0.99, recommendation="approve")
    posting_result = sample_posting_result(success=True)
    workflows = {
        "triage": FakeWorkflow(FakeAsyncStream([FakeEvent(triage_result.model_dump(mode="json"))])),
        "extractor": FakeWorkflow(extraction_result.model_dump(mode="json")),
        "coherence": FakeWorkflow(coherence_result.model_dump(mode="json")),
        "validator": FakeWorkflow(validation_result.model_dump(mode="json")),
        "inventory": FakeWorkflow(posting_result.model_dump(mode="json")),
    }

    with patch("src.agents.pipeline.SequentialBuilder", side_effect=_patch_sequential_builder(workflows)):
        result = await build_pipeline().run(
            PipelineDocumentInput(document_reference="https://storage/account/albaran.pdf")
        )

    assert result.routing_decision == "posted"
    assert result.validation == validation_result
    assert result.inventory == posting_result


@pytest.mark.asyncio
async def test_full_pipeline_routes_to_hitl_when_validation_requires_review() -> None:
    validation_result = sample_validation(overall_match_pct=0.9, recommendation="hitl_review")
    workflows = {
        "triage": FakeWorkflow(sample_triage_result().model_dump(mode="json")),
        "extractor": FakeWorkflow(sample_extraction().model_dump(mode="json")),
        "coherence": FakeWorkflow(sample_coherence_result().model_dump(mode="json")),
        "validator": FakeWorkflow(validation_result.model_dump(mode="json")),
    }

    with patch("src.agents.pipeline.SequentialBuilder", side_effect=_patch_sequential_builder(workflows)):
        result = await build_pipeline().run(
            PipelineDocumentInput(document_reference="https://storage/account/albaran.pdf")
        )

    assert result.routing_decision == "hitl_review"
    assert result.inventory is None
    assert result.skipped_steps == ["inventory"]


@pytest.mark.asyncio
async def test_full_pipeline_stops_after_reject_decision() -> None:
    rejected_triage = sample_triage_result(
        document_type=DocumentType.UNKNOWN,
        confidence=0.22,
        routing_decision="reject",
        reasoning="The document is not a delivery note.",
    )
    workflows = {"triage": FakeWorkflow(rejected_triage.model_dump(mode="json"))}

    with patch("src.agents.pipeline.SequentialBuilder", side_effect=_patch_sequential_builder(workflows)):
        result = await build_pipeline().run(
            PipelineDocumentInput(document_reference="https://storage/account/flyer.pdf")
        )

    assert result.routing_decision == "reject"
    assert result.extraction is None
    assert result.validation is None
    assert result.inventory is None
