from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import patch

import pytest

from src.agents.pipeline import AlbaranPipeline, PipelineDocumentInput
from src.models import DocumentType
from tests.fixtures.sample_albarans import sample_coherence_result, sample_extraction, sample_triage_result
from tests.fixtures.sample_validations import sample_posting_result, sample_validation

pytestmark = pytest.mark.unit


class FakeEvent:
    def __init__(self, data: Any) -> None:
        self.data = data


class FakeAsyncStream:
    def __init__(self, events: list[Any]) -> None:
        self._events = iter(events)

    def __aiter__(self) -> AsyncIterator[Any]:
        return self

    async def __anext__(self) -> Any:
        try:
            return next(self._events)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FakeWorkflow:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.payloads: list[Any] = []

    def run(self, payload: Any, *, stream: bool) -> Any:
        assert stream is True
        self.payloads.append(payload)
        return self.response


def build_pipeline() -> AlbaranPipeline:
    return AlbaranPipeline(
        client=object(),
        agents={
            "triage": object(),
            "extractor": object(),
            "coherence": object(),
            "validator": object(),
            "inventory": object(),
        },
    )


@pytest.mark.asyncio
async def test_full_pipeline_happy_path_posts_inventory() -> None:
    triage_result = sample_triage_result()
    extraction_result = sample_extraction()
    coherence_result = sample_coherence_result()
    validation_result = sample_validation(overall_match_pct=0.99, recommendation="approve")
    posting_result = sample_posting_result(success=True)
    workflows = {
        "albaran-triage": FakeWorkflow(FakeAsyncStream([FakeEvent(triage_result.model_dump(mode="json"))])),
        "albaran-extraction": FakeWorkflow(extraction_result.model_dump(mode="json")),
        "albaran-coherence": FakeWorkflow(coherence_result.model_dump(mode="json")),
        "albaran-validation": FakeWorkflow(validation_result.model_dump(mode="json")),
        "albaran-inventory": FakeWorkflow(posting_result.model_dump(mode="json")),
    }

    def fake_build_sequential_workflow(*, name: str, participants: list[Any]) -> FakeWorkflow:
        assert participants
        return workflows[name]

    with patch("src.agents.pipeline.build_sequential_workflow", side_effect=fake_build_sequential_workflow):
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
        "albaran-triage": FakeWorkflow(sample_triage_result().model_dump(mode="json")),
        "albaran-extraction": FakeWorkflow(sample_extraction().model_dump(mode="json")),
        "albaran-coherence": FakeWorkflow(sample_coherence_result().model_dump(mode="json")),
        "albaran-validation": FakeWorkflow(validation_result.model_dump(mode="json")),
    }

    def fake_build_sequential_workflow(*, name: str, participants: list[Any]) -> FakeWorkflow:
        assert participants
        return workflows[name]

    with patch("src.agents.pipeline.build_sequential_workflow", side_effect=fake_build_sequential_workflow):
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

    def fake_build_sequential_workflow(*, name: str, participants: list[Any]) -> FakeWorkflow:
        assert participants
        return {"albaran-triage": FakeWorkflow(rejected_triage.model_dump(mode="json"))}[name]

    with patch("src.agents.pipeline.build_sequential_workflow", side_effect=fake_build_sequential_workflow):
        result = await build_pipeline().run(
            PipelineDocumentInput(document_reference="https://storage/account/flyer.pdf")
        )

    assert result.routing_decision == "reject"
    assert result.extraction is None
    assert result.validation is None
    assert result.inventory is None
