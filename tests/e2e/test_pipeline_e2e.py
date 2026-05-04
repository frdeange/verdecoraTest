from __future__ import annotations

from unittest.mock import patch

import pytest

from src.services.orchestrator.handler import handle_message
from tests.e2e.conftest import FakeReceivedMessage
from tests.fixtures.sample_albarans import sample_coherence_result, sample_extraction, sample_triage_result
from tests.fixtures.sample_validations import sample_posting_result, sample_validation

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_pipeline_e2e_happy_path_updates_cosmos_and_preserves_agent_handoffs(
    flow0_handler: tuple[object, object],
    sample_blob_event: dict[str, object],
    orchestrator_factory: object,
    workflow_factory: object,
    fake_receiver: object,
    cosmos_store: object,
    ocr_payload: dict[str, object],
) -> None:
    flow0, flow0_sender = flow0_handler
    assert flow0.handle_message(sample_blob_event) is True
    forwarded_payload = flow0_sender.messages[0]

    triage_result = sample_triage_result()
    extraction_result = sample_extraction()
    coherence_result = sample_coherence_result()
    validation_result = sample_validation(overall_match_pct=0.99, recommendation="approve")
    posting_result = sample_posting_result(success=True)
    workflows, fake_builder = workflow_factory(
        {
            "triage": [triage_result.model_dump(mode="json")],
            "extractor": extraction_result.model_dump(mode="json"),
            "coherence": coherence_result.model_dump(mode="json"),
            "validator": validation_result.model_dump(mode="json"),
            "inventory": posting_result.model_dump(mode="json"),
        }
    )
    orchestrator, service_bus_client = orchestrator_factory()
    message = FakeReceivedMessage(forwarded_payload)

    with patch("src.agents.pipeline.SequentialBuilder", side_effect=fake_builder):
        result = await handle_message(orchestrator, receiver=fake_receiver, message=message)

    assert result.processing_id == forwarded_payload["albaran_id"]
    assert result.status == "completed"
    assert result.routing_decision == "posted"
    assert result.pipeline_result["inventory"]["receipt_number"] == posting_result.receipt_number
    assert cosmos_store.items[result.processing_id]["status"] == "completed"
    assert fake_receiver.completed_messages == [message]
    assert not service_bus_client.sent_messages

    assert workflows["triage"].payloads == [ocr_payload["content"]]
    assert workflows["extractor"].payloads == [ocr_payload]
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
