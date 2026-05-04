from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.agents.communication_agent import CommunicationAgentService
from src.models.communication import EscalationLevel, HITLDecision
from src.models.inventory import PostingResult
from src.services.escalation.config import EscalationConfig
from src.services.escalation.scheduler import EscalationScheduler
from src.services.hitl_webform.callbacks import HITLCallbackHandler
from src.services.hitl_webform.config import HITLWebformConfig
from src.services.hitl_webform.main import create_app
from src.services.orchestrator.handler import handle_message
from tests.e2e.conftest import FakeReceivedMessage
from tests.fixtures.sample_albarans import sample_coherence_result, sample_extraction, sample_triage_result
from tests.fixtures.sample_validations import sample_validation

pytestmark = pytest.mark.e2e


class InMemoryReviewStore:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}
        self.saved_decisions: list[dict[str, Any]] = []

    async def get_review_record(self, albaran_id: str) -> dict[str, Any] | None:
        record = self.items.get(albaran_id)
        return dict(record) if record is not None else None

    async def save_decision(self, decision: Any) -> dict[str, Any]:
        payload = decision.model_dump(mode="json")
        self.saved_decisions.append(payload)
        record = dict(self.items[payload["albaran_id"]])
        record.update({"status": "decided", "hitl_decision": payload})
        self.items[payload["albaran_id"]] = record
        return dict(record)

    async def upsert_item(self, document: dict[str, Any]) -> dict[str, Any]:
        self.items[str(document["id"])] = dict(document)
        return dict(document)

    async def list_pending_reviews(self) -> list[dict[str, Any]]:
        return [
            dict(item) for item in self.items.values() if item.get("status") in {"pending", "reminded", "escalated"}
        ]


class FakeDecisionPublisher:
    def __init__(self) -> None:
        self.decisions: list[dict[str, Any]] = []

    async def publish(self, decision: Any) -> None:
        self.decisions.append(decision.model_dump(mode="json"))


@pytest.mark.asyncio
async def test_hitl_e2e_discrepancy_email_approve_inventory_posted(
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
    orchestrator, _service_bus_client = orchestrator_factory()
    message = FakeReceivedMessage(forwarded_payload)

    with patch("src.agents.pipeline.SequentialBuilder", side_effect=fake_build):
        orchestration_result = await handle_message(orchestrator, receiver=fake_receiver, message=message)

    assert orchestration_result.status == "hitl_pending"
    review_store = InMemoryReviewStore()
    review_record = {
        "id": orchestration_result.processing_id,
        "created_at": datetime(2026, 5, 4, 9, 0, tzinfo=UTC).isoformat(),
        "status": "pending",
        "recipient_email": "compras@verdecora.example.com",
        "callback_url": f"https://hitl.example.com/review/{orchestration_result.processing_id}",
        "pdf_sas_url": "https://storage.example.com/alb-hitl-e2e-approve.pdf?sig=abc",
        "pipeline_result": orchestration_result.pipeline_result,
    }
    await review_store.upsert_item(review_record)

    sent_notifications: list[Any] = []
    communication_service = CommunicationAgentService(
        send_notification_tool=lambda notification: sent_notifications.append(notification),
        records_container=review_store,
        now_provider=lambda: datetime(2026, 5, 4, 9, 0, tzinfo=UTC),
    )
    notification = await communication_service.handle_hitl_review(review_record)

    publisher = FakeDecisionPublisher()
    app = create_app(
        config=HITLWebformConfig(allow_local_email_bearer=True),
        review_store=review_store,
        decision_publisher=publisher,
    )
    with TestClient(app) as client:
        response = client.post(
            f"/review/{orchestration_result.processing_id}/decide",
            headers={"Authorization": "Bearer reviewer@verdecora.example.com"},
            json={"decision": "approve", "notes": "Mercancía validada manualmente."},
        )

    posted_payloads: list[dict[str, Any]] = []

    async def fake_inventory_processor(payload: dict[str, Any]) -> PostingResult:
        posted_payloads.append(payload)
        return PostingResult(success=True, receipt_number="RCPT-2026-2001", posted_lines=1)

    callback_handler = HITLCallbackHandler(review_store, inventory_processor=fake_inventory_processor)
    callback_result = await callback_handler.handle_decision(HITLDecision.model_validate(publisher.decisions[0]))

    assert notification.escalation_level is EscalationLevel.INITIAL
    assert response.status_code == 200
    assert review_store.saved_decisions[0]["decision"] == "approve"
    assert len(sent_notifications) == 1
    assert posted_payloads[0]["decision"]["decision"] == "approve"
    assert callback_result["status"] == "completed"
    assert callback_result["inventory_result"]["receipt_number"] == "RCPT-2026-2001"
    assert workflows["validator"].payloads


@pytest.mark.asyncio
async def test_hitl_e2e_discrepancy_email_rejects_albaran(
    flow0_handler: tuple[object, object],
    sample_blob_event: dict[str, object],
    orchestrator_factory: object,
    workflow_factory: object,
    fake_receiver: object,
) -> None:
    flow0, flow0_sender = flow0_handler
    assert flow0.handle_message(sample_blob_event) is True
    forwarded_payload = flow0_sender.messages[0]

    workflows, fake_build = workflow_factory(
        {
            "triage": [sample_triage_result().model_dump(mode="json")],
            "extractor": sample_extraction().model_dump(mode="json"),
            "coherence": sample_coherence_result().model_dump(mode="json"),
            "validator": sample_validation(overall_match_pct=0.86, recommendation="hitl_review").model_dump(
                mode="json"
            ),
        }
    )
    orchestrator, _service_bus_client = orchestrator_factory()

    with patch("src.agents.pipeline.SequentialBuilder", side_effect=fake_build):
        orchestration_result = await handle_message(
            orchestrator,
            receiver=fake_receiver,
            message=FakeReceivedMessage(forwarded_payload),
        )

    review_store = InMemoryReviewStore()
    await review_store.upsert_item(
        {
            "id": orchestration_result.processing_id,
            "created_at": datetime(2026, 5, 4, 9, 0, tzinfo=UTC).isoformat(),
            "status": "pending",
            "recipient_email": "compras@verdecora.example.com",
            "callback_url": f"https://hitl.example.com/review/{orchestration_result.processing_id}",
            "pdf_sas_url": "https://storage.example.com/alb-hitl-e2e-reject.pdf?sig=abc",
            "pipeline_result": orchestration_result.pipeline_result,
        }
    )
    communication_service = CommunicationAgentService(
        send_notification_tool=lambda notification: None,
        records_container=review_store,
        now_provider=lambda: datetime(2026, 5, 4, 9, 0, tzinfo=UTC),
    )
    await communication_service.handle_hitl_review(
        await review_store.get_review_record(orchestration_result.processing_id) or {}
    )

    publisher = FakeDecisionPublisher()
    app = create_app(
        config=HITLWebformConfig(allow_local_email_bearer=True),
        review_store=review_store,
        decision_publisher=publisher,
    )
    with TestClient(app) as client:
        response = client.post(
            f"/review/{orchestration_result.processing_id}/decide",
            headers={"Authorization": "Bearer reviewer@verdecora.example.com"},
            json={"decision": "reject", "notes": "El albarán no coincide con BC."},
        )

    callback_handler = HITLCallbackHandler(
        review_store,
        inventory_processor=lambda payload: PostingResult(success=True, posted_lines=0),
    )
    callback_result = await callback_handler.handle_decision(HITLDecision.model_validate(publisher.decisions[0]))

    assert response.status_code == 200
    assert callback_result["status"] == "rejected"
    assert callback_result["routing_decision"] == "reject"
    assert callback_result["inventory_result"] is None
    assert workflows["validator"].payloads


@pytest.mark.asyncio
async def test_hitl_e2e_no_response_triggers_reminder_and_escalation() -> None:
    review_store = InMemoryReviewStore()
    created_at = datetime(2026, 5, 4, 9, 0, tzinfo=UTC)
    await review_store.upsert_item(
        {
            "id": "alb-hitl-timeout-001",
            "created_at": created_at.isoformat(),
            "status": "pending",
            "recipient_email": "compras@verdecora.example.com",
            "callback_url": "https://hitl.example.com/review/alb-hitl-timeout-001",
            "pdf_sas_url": "https://storage.example.com/alb-hitl-timeout-001.pdf?sig=abc",
            "pipeline_result": {
                "extraction": {"header": {"document_number": "ALB-HITL-TIMEOUT-001", "supplier_name": "Royal Canin"}},
                "validation": {"discrepancies": ["Cantidad distinta en la línea 1."]},
            },
        }
    )
    sent_levels: list[EscalationLevel] = []
    communication_service = CommunicationAgentService(
        send_notification_tool=lambda notification: sent_levels.append(notification.escalation_level),
        records_container=review_store,
        now_provider=lambda: created_at,
    )

    initial_record = await review_store.get_review_record("alb-hitl-timeout-001")
    assert initial_record is not None
    await communication_service.handle_hitl_review(initial_record)

    scheduler = EscalationScheduler(review_store, communication_service, config=EscalationConfig())
    reminder_notifications = await scheduler.run_once(now=created_at + timedelta(hours=25))
    escalation_notifications = await scheduler.run_once(now=created_at + timedelta(hours=49))

    assert [item.albaran_id for item in reminder_notifications] == ["alb-hitl-timeout-001"]
    assert [item.albaran_id for item in escalation_notifications] == ["alb-hitl-timeout-001"]
    assert sent_levels == [
        EscalationLevel.INITIAL,
        EscalationLevel.REMINDER_24H,
        EscalationLevel.ESCALATION_48H,
    ]
    assert review_store.items["alb-hitl-timeout-001"]["status"] == "escalated"
