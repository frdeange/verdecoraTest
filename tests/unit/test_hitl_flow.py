from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.agents.communication_agent import CommunicationAgentService
from src.models.communication import EscalationLevel, HITLDecision
from src.models.inventory import PostingResult
from src.services.escalation import timer
from src.services.hitl_webform import sas
from src.services.hitl_webform.callbacks import HITLCallbackHandler
from src.services.hitl_webform.config import HITLWebformConfig
from src.services.hitl_webform.main import create_app

pytestmark = pytest.mark.unit


class InMemoryReviewStore:
    def __init__(self, record: dict[str, Any]) -> None:
        self.record = dict(record)
        self.saved_decisions: list[dict[str, Any]] = []
        self.upserts: list[dict[str, Any]] = []

    async def get_review_record(self, albaran_id: str) -> dict[str, Any] | None:
        return dict(self.record) if albaran_id == self.record["id"] else None

    async def save_decision(self, decision: Any) -> dict[str, Any]:
        payload = decision.model_dump(mode="json")
        self.saved_decisions.append(payload)
        self.record.update(
            {
                "status": "decided",
                "hitl_decision": payload,
                "reviewer_email": payload["reviewer_email"],
            }
        )
        return dict(self.record)

    async def upsert_item(self, document: dict[str, Any]) -> dict[str, Any]:
        self.record = dict(document)
        self.upserts.append(dict(document))
        return dict(self.record)


class FakePublisher:
    def __init__(self) -> None:
        self.decisions: list[dict[str, Any]] = []

    async def publish(self, decision: Any) -> None:
        self.decisions.append(decision.model_dump(mode="json"))


class FakeEscalationStore:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records

    async def list_pending_reviews(self) -> list[dict[str, Any]]:
        return list(self.records)

    async def close(self) -> None:
        return None


def build_review_record(*, now: datetime | None = None) -> dict[str, Any]:
    current_time = now or datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    return {
        "id": "alb-hitl-001",
        "created_at": (current_time - timedelta(hours=30)).isoformat(),
        "recipient_email": "compras@verdecora.example.com",
        "callback_url": "https://hitl.example.com/review/alb-hitl-001",
        "pdf_sas_url": "https://storage.example.com/alb-hitl-001.pdf?sig=abc",
        "pipeline_result": {
            "extraction": {
                "header": {
                    "document_number": "ALB-HITL-001",
                    "supplier_name": "Herstera Garden",
                }
            },
            "validation": {
                "discrepancies": [
                    "Cantidad distinta en la línea 1.",
                    "Precio unitario fuera de tolerancia.",
                ]
            },
        },
    }


def test_a6_communication_agent_email_generation() -> None:
    review_record = build_review_record()
    service = CommunicationAgentService(now_provider=lambda: datetime(2026, 5, 4, 12, 0, tzinfo=UTC))

    notification = service.build_notification(review_record, escalation_level=EscalationLevel.INITIAL)

    assert notification.albaran_id == "alb-hitl-001"
    assert notification.recipient_email == "compras@verdecora.example.com"
    assert "Revisión inicial requerida" in notification.subject
    assert "Cantidad distinta en la línea 1." in notification.body_html
    assert notification.callback_url.endswith("/review/alb-hitl-001")
    assert notification.pdf_sas_url.endswith("alb-hitl-001.pdf?sig=abc")


@pytest.mark.asyncio
async def test_escalation_timer_triggers_24h_48h_and_72h(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)
    records = [
        {"id": "alb-24h", "created_at": (now - timedelta(hours=25)).isoformat(), "escalation_level": "initial"},
        {"id": "alb-48h", "created_at": (now - timedelta(hours=49)).isoformat(), "escalation_level": "reminder_24h"},
        {"id": "alb-72h", "created_at": (now - timedelta(hours=73)).isoformat(), "escalation_level": "escalation_48h"},
    ]
    sent_levels: list[EscalationLevel] = []

    class FakeCommunicationService:
        def __init__(self, records_container: Any) -> None:
            self.records_container = records_container

        async def handle_hitl_review(
            self,
            review_record: dict[str, Any],
            *,
            escalation_level: EscalationLevel,
        ) -> dict[str, Any]:
            sent_levels.append(escalation_level)
            return {
                "albaran_id": review_record["id"],
                "escalation_level": escalation_level.value,
            }

    monkeypatch.setattr(timer, "CosmosEscalationStore", lambda config: FakeEscalationStore(records))
    monkeypatch.setattr(timer, "CommunicationAgentService", FakeCommunicationService)

    notifications = await timer.run_timer_cycle(now=now)

    assert [item["albaran_id"] for item in notifications] == ["alb-24h", "alb-48h", "alb-72h"]
    assert sent_levels == [
        EscalationLevel.REMINDER_24H,
        EscalationLevel.ESCALATION_48H,
        EscalationLevel.FINAL_72H,
    ]


def test_webform_routes_support_get_review_and_post_decision() -> None:
    store = InMemoryReviewStore(build_review_record())
    publisher = FakePublisher()
    app = create_app(
        config=HITLWebformConfig(allow_local_email_bearer=True),
        review_store=store,
        decision_publisher=publisher,
    )

    with TestClient(app) as client:
        review_response = client.get(
            "/review/alb-hitl-001",
            headers={"Authorization": "Bearer reviewer@verdecora.example.com"},
        )
        decision_response = client.post(
            "/review/alb-hitl-001/decide",
            headers={"Authorization": "Bearer reviewer@verdecora.example.com"},
            json={"decision": "approve", "notes": "Todo correcto."},
        )

    assert review_response.status_code == 200
    assert "Cantidad distinta en la línea 1." in review_response.text
    assert decision_response.status_code == 200
    assert decision_response.json()["decision"]["reviewer_email"] == "reviewer@verdecora.example.com"
    assert store.saved_decisions[0]["decision"] == "approve"
    assert publisher.decisions[0]["decision"] == "approve"


@pytest.mark.asyncio
async def test_callback_handler_approve_posts_inventory() -> None:
    review_store = InMemoryReviewStore(build_review_record())
    inventory_calls: list[dict[str, Any]] = []

    async def fake_inventory_processor(payload: dict[str, Any]) -> PostingResult:
        inventory_calls.append(payload)
        return PostingResult(success=True, receipt_number="RCPT-2026-1001", posted_lines=1)

    handler = HITLCallbackHandler(review_store, inventory_processor=fake_inventory_processor)
    updated = await handler.handle_decision(
        HITLDecision(
            albaran_id="alb-hitl-001",
            decision="approve",
            reviewer_email="reviewer@verdecora.example.com",
            decided_at=datetime(2026, 5, 5, 8, 30, tzinfo=UTC),
        )
    )

    assert inventory_calls[0]["validation"]["discrepancies"] == [
        "Cantidad distinta en la línea 1.",
        "Precio unitario fuera de tolerancia.",
    ]
    assert updated["status"] == "completed"
    assert updated["routing_decision"] == "posted"
    assert updated["inventory_result"]["receipt_number"] == "RCPT-2026-1001"


@pytest.mark.asyncio
async def test_callback_handler_cancellation_path_marks_record_cancelled() -> None:
    review_store = InMemoryReviewStore(build_review_record())
    handler = HITLCallbackHandler(
        review_store,
        inventory_processor=lambda payload: PostingResult(success=True, posted_lines=0),
        now_provider=lambda: datetime(2026, 5, 5, 9, 0, tzinfo=UTC),
    )

    updated = await handler.cancel_review(
        "alb-hitl-001",
        reviewer_email="reviewer@verdecora.example.com",
        notes="La revisión se cancela por documento duplicado.",
    )

    assert updated["status"] == "cancelled"
    assert updated["routing_decision"] == "cancelled"
    assert updated["reviewer_email"] == "reviewer@verdecora.example.com"
    assert updated["cancellation_notes"] == "La revisión se cancela por documento duplicado."


def test_sas_url_generation_for_pdfs(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeBlobServiceClient:
        def __init__(self, *, account_url: str, credential: object) -> None:
            captured["account_url"] = account_url
            captured["credential"] = credential
            self.account_name = "stverdecora"

        def get_blob_client(self, *, container: str, blob: str) -> Any:
            captured["blob_ref"] = (container, blob)
            return type("BlobClient", (), {"url": f"https://stverdecora.blob.core.windows.net/{container}/{blob}"})()

        def get_user_delegation_key(self, start: datetime, expiry: datetime) -> str:
            captured["delegation_window"] = (start, expiry)
            return "delegation-key"

    class FakeBlobSasPermissions:
        def __init__(self, *, read: bool) -> None:
            captured["read_permission"] = read

    def fake_generate_blob_sas(**kwargs: object) -> str:
        captured["sas_kwargs"] = kwargs
        return "sig=token"

    monkeypatch.setattr(sas, "BlobServiceClient", FakeBlobServiceClient)
    monkeypatch.setattr(sas, "BlobSasPermissions", FakeBlobSasPermissions)
    monkeypatch.setattr(sas, "generate_blob_sas", fake_generate_blob_sas)
    monkeypatch.setattr(sas, "get_managed_identity_credential", lambda: object())

    sas_url = sas.generate_pdf_sas_url(
        "https://stverdecora.blob.core.windows.net",
        "albaranes-raw",
        "alb-hitl-001.pdf",
    )

    assert captured["blob_ref"] == ("albaranes-raw", "alb-hitl-001.pdf")
    assert captured["read_permission"] is True
    assert captured["sas_kwargs"]["user_delegation_key"] == "delegation-key"
    assert sas_url.endswith("?sig=token")
