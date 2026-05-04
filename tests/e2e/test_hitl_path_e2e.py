from __future__ import annotations

from unittest.mock import patch

import pytest

from src.services.orchestrator.handler import handle_message
from tests.e2e.conftest import FakeReceivedMessage
from tests.fixtures.sample_albarans import sample_coherence_result, sample_extraction, sample_triage_result
from tests.fixtures.sample_validations import sample_validation

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_hitl_path_e2e_stops_pipeline_and_notifies_hitl_queue(
    flow0_handler: tuple[object, object],
    sample_blob_event: dict[str, object],
    orchestrator_factory: object,
    workflow_factory: object,
    fake_receiver: object,
    cosmos_store: object,
) -> None:
    flow0, flow0_sender = flow0_handler
    assert flow0.handle_message(sample_blob_event) is True
    forwarded_payload = flow0_sender.messages[0]

    validation_result = sample_validation(overall_match_pct=0.88, recommendation="hitl_review")
    workflows, fake_build = workflow_factory(
        {
            "triage": [sample_triage_result().model_dump(mode="json")],
            "extractor": sample_extraction().model_dump(mode="json"),
            "coherence": sample_coherence_result().model_dump(mode="json"),
            "validator": validation_result.model_dump(mode="json"),
        }
    )
    orchestrator, service_bus_client = orchestrator_factory()
    message = FakeReceivedMessage(forwarded_payload)

    with patch("src.agents.pipeline.SequentialBuilder", side_effect=fake_build):
        result = await handle_message(orchestrator, receiver=fake_receiver, message=message)

    assert result.status == "hitl_pending"
    assert result.routing_decision == "hitl_review"
    assert result.pipeline_result["inventory"] is None
    assert cosmos_store.items[result.processing_id]["status"] == "hitl_pending"
    assert fake_receiver.completed_messages == [message]
    assert len(service_bus_client.sent_messages) == 1
    assert service_bus_client.sent_messages[0]["queue_name"] == orchestrator.config.hitl_queue_name
    assert service_bus_client.sent_messages[0]["payload"]["processing_id"] == result.processing_id
    assert workflows["validator"].payloads
