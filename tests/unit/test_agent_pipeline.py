from __future__ import annotations

from collections.abc import AsyncIterator
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
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_pipeline_creation_with_all_agents() -> None:
    pipeline = AlbaranPipeline(
        agents={
            "triage": object(),
            "extractor": object(),
            "coherence": object(),
            "validator": object(),
            "inventory": object(),
        },
    )

    assert set(pipeline.agents) == {"triage", "extractor", "coherence", "validator", "inventory"}


@pytest.mark.asyncio
async def test_pipeline_run_with_mocked_agents() -> None:
    triage_result = sample_triage_result()
    extraction_result = sample_extraction()
    coherence_result = sample_coherence_result()
    validation_result = sample_validation_result()
    posting_result = sample_posting_result()
    triage_workflow = FakeWorkflow(
        FakeAsyncStream([FakeEvent({"ignored": True}), FakeEvent(triage_result.model_dump(mode="json"))])
    )
    extraction_workflow = FakeWorkflow(extraction_result.model_dump(mode="json"))
    coherence_workflow = FakeWorkflow(coherence_result.model_dump_json())
    validation_workflow = FakeWorkflow(validation_result.model_dump(mode="json"))
    inventory_workflow = FakeWorkflow(posting_result.model_dump_json())
    workflows = {
        "albaran-triage": triage_workflow,
        "albaran-extraction": extraction_workflow,
        "albaran-coherence": coherence_workflow,
        "albaran-validation": validation_workflow,
        "albaran-inventory": inventory_workflow,
    }

    def fake_build_sequential_workflow(*, name: str, participants: list[Any]) -> FakeWorkflow:
        assert participants
        return workflows[name]

    pipeline = AlbaranPipeline(
        agents={
            "triage": object(),
            "extractor": object(),
            "coherence": object(),
            "validator": object(),
            "inventory": object(),
        },
    )
    input_data = PipelineDocumentInput(
        document_reference="https://storage/account/albaran.pdf",
        raw_text="ALBARAN DE ENTREGA",
        ocr_payload={"pages": [{"pageNumber": 1}]},
    )

    with patch("src.agents.pipeline.build_sequential_workflow", side_effect=fake_build_sequential_workflow):
        result = await pipeline.run(input_data)

    assert isinstance(result, PipelineRunResult)
    assert result.triage == triage_result
    assert result.extraction == extraction_result
    assert result.coherence == coherence_result
    assert result.validation == validation_result
    assert result.inventory == posting_result
    assert result.routing_decision == "posted"
    assert triage_workflow.payloads == ["ALBARAN DE ENTREGA"]
    assert extraction_workflow.payloads == [{"pages": [{"pageNumber": 1}]}]
    assert coherence_workflow.payloads == [extraction_result.model_dump(mode="json")]
    assert validation_workflow.payloads == [
        {
            "extraction": extraction_result.model_dump(mode="json"),
            "coherence": coherence_result.model_dump(mode="json"),
        }
    ]
    assert inventory_workflow.payloads == [
        {
            "validation": validation_result.model_dump(mode="json"),
            "extraction": extraction_result.model_dump(mode="json"),
        }
    ]


@pytest.mark.asyncio
async def test_pipeline_propagates_agent_failures() -> None:
    pipeline = AlbaranPipeline(
        agents={
            "triage": object(),
            "extractor": object(),
            "coherence": object(),
            "validator": object(),
            "inventory": object(),
        },
    )

    def fake_build_sequential_workflow(*, name: str, participants: list[Any]) -> FakeWorkflow:
        _ = participants
        if name == "albaran-triage":
            return FakeWorkflow(RuntimeError("triage failed"))
        return FakeWorkflow({})

    with (
        patch("src.agents.pipeline.build_sequential_workflow", side_effect=fake_build_sequential_workflow),
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
    extraction_workflow = FakeWorkflow(extraction_result.model_dump(mode="json"))
    coherence_workflow = FakeWorkflow(coherence_result.model_dump(mode="json"))
    validation_workflow = FakeWorkflow(validation_result.model_dump(mode="json"))
    inventory_workflow = FakeWorkflow(posting_result.model_dump(mode="json"))
    calls: list[str] = []

    def fake_build_sequential_workflow(*, name: str, participants: list[Any]) -> FakeWorkflow:
        calls.append(name)
        assert participants
        return {
            "albaran-extraction": extraction_workflow,
            "albaran-coherence": coherence_workflow,
            "albaran-validation": validation_workflow,
            "albaran-inventory": inventory_workflow,
        }[name]

    pipeline = AlbaranPipeline(
        config=config,
        agents={
            "triage": object(),
            "extractor": object(),
            "coherence": object(),
            "validator": object(),
            "inventory": object(),
        },
    )

    with patch("src.agents.pipeline.build_sequential_workflow", side_effect=fake_build_sequential_workflow):
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
    assert calls == ["albaran-extraction", "albaran-coherence", "albaran-validation", "albaran-inventory"]


@pytest.mark.asyncio
async def test_pipeline_stops_after_non_extract_triage_result() -> None:
    rejected_triage = sample_triage_result(
        document_type=DocumentType.UNKNOWN,
        confidence=0.12,
        routing_decision="reject",
        reasoning="Unrelated marketing brochure.",
    )
    triage_workflow = FakeWorkflow(rejected_triage.model_dump(mode="json"))

    def fake_build_sequential_workflow(*, name: str, participants: list[Any]) -> FakeWorkflow:
        assert participants
        return {"albaran-triage": triage_workflow}[name]

    pipeline = AlbaranPipeline(
        agents={
            "triage": object(),
            "extractor": object(),
            "coherence": object(),
            "validator": object(),
            "inventory": object(),
        },
    )

    with patch("src.agents.pipeline.build_sequential_workflow", side_effect=fake_build_sequential_workflow):
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

    def fake_build_sequential_workflow(*, name: str, participants: list[Any]) -> FakeWorkflow:
        assert participants
        return {
            "albaran-triage": FakeWorkflow(sample_triage_result().model_dump(mode="json")),
            "albaran-extraction": FakeWorkflow(extraction_result.model_dump(mode="json")),
            "albaran-coherence": FakeWorkflow(coherence_result.model_dump(mode="json")),
            "albaran-validation": FakeWorkflow(validation_result.model_dump(mode="json")),
        }[name]

    pipeline = AlbaranPipeline(
        agents={
            "triage": object(),
            "extractor": object(),
            "coherence": object(),
            "validator": object(),
            "inventory": object(),
        },
    )

    with patch("src.agents.pipeline.build_sequential_workflow", side_effect=fake_build_sequential_workflow):
        result = await pipeline.run({"document_reference": "https://storage/account/albaran.pdf"})

    assert result.validation == validation_result
    assert result.inventory is None
    assert result.routing_decision == "hitl_review"
    assert result.skipped_steps == ["inventory"]


@pytest.mark.asyncio
async def test_pipeline_skips_validation_and_inventory_when_coherence_is_skipped() -> None:
    extraction_result = sample_extraction()

    def fake_build_sequential_workflow(*, name: str, participants: list[Any]) -> FakeWorkflow:
        assert participants
        return {"albaran-extraction": FakeWorkflow(extraction_result.model_dump(mode="json"))}[name]

    pipeline = AlbaranPipeline(
        config=AgentsConfig.model_validate(
            {
                "skip_triage_suppliers": ["HERSTERA"],
                "thresholds": {"low_value_coherence_threshold": 250.0},
            }
        ),
        agents={
            "triage": object(),
            "extractor": object(),
            "coherence": object(),
            "validator": object(),
            "inventory": object(),
        },
    )

    with patch("src.agents.pipeline.build_sequential_workflow", side_effect=fake_build_sequential_workflow):
        result = await pipeline.run(
            {
                "document_reference": "https://storage/account/albaran.pdf",
                "total_amount": 99.0,
                "supplier_hint": "HERSTERA",
            }
        )

    assert result.extraction == extraction_result
    assert result.coherence is None
    assert result.validation is None
    assert result.inventory is None
    assert result.routing_decision == "extract"
    assert result.skipped_steps == ["triage", "coherence", "validation", "inventory"]
