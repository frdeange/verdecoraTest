from __future__ import annotations

from unittest.mock import patch

import pytest

from src.models import DocumentType
from src.services.orchestrator.handler import handle_message
from tests.e2e.conftest import FakeReceivedMessage
from tests.fixtures.sample_albarans import sample_triage_result

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_reject_path_e2e_stops_after_triage_and_marks_record_rejected(
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

    rejected_triage = sample_triage_result(
        document_type=DocumentType.UNKNOWN,
        confidence=0.18,
        routing_decision="reject",
        reasoning="Documento desconocido; no corresponde a un albarán.",
    )
    workflows, fake_build = workflow_factory({"triage": [rejected_triage.model_dump(mode="json")]})
    orchestrator, service_bus_client = orchestrator_factory()
    message = FakeReceivedMessage(forwarded_payload)

    with patch("src.agents.pipeline.SequentialBuilder", side_effect=fake_build):
        result = await handle_message(orchestrator, receiver=fake_receiver, message=message)

    assert result.status == "rejected"
    assert result.routing_decision == "reject"
    assert result.pipeline_result["extraction"] is None
    assert result.pipeline_result["validation"] is None
    assert cosmos_store.items[result.processing_id]["status"] == "rejected"
    assert fake_receiver.completed_messages == [message]
    assert workflows["triage"].payloads
    assert not service_bus_client.sent_messages
