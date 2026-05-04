from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from src.agents.communication_agent import CommunicationAgentService
from src.models.communication import EscalationLevel
from src.services.escalation.config import EscalationConfig
from src.services.escalation.scheduler import EscalationScheduler

pytestmark = pytest.mark.unit


class FakeEscalationStore:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = records
        self.upserts: list[dict[str, Any]] = []

    async def list_pending_reviews(self) -> list[dict[str, Any]]:
        return list(self._records)

    async def upsert_item(self, document: dict[str, Any]) -> dict[str, Any]:
        self.upserts.append(document)
        return document


@pytest.mark.asyncio
async def test_escalation_scheduler_sends_reminder_escalation_and_final_notice() -> None:
    now = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)
    store = FakeEscalationStore(
        [
            {
                "id": "alb-reminder",
                "recipient_email": "hitl@verdecora.example.com",
                "created_at": (now - timedelta(hours=25)).isoformat(),
                "escalation_level": "initial",
            },
            {
                "id": "alb-escalated",
                "recipient_email": "hitl@verdecora.example.com",
                "created_at": (now - timedelta(hours=49)).isoformat(),
                "escalation_level": "reminder_24h",
            },
            {
                "id": "alb-expired",
                "recipient_email": "hitl@verdecora.example.com",
                "created_at": (now - timedelta(hours=73)).isoformat(),
                "escalation_level": "escalation_48h",
            },
        ]
    )
    sent_notifications = []

    def fake_send(notification: Any) -> dict[str, str]:
        sent_notifications.append(notification)
        return {"message_id": notification.albaran_id, "status": "queued"}

    service = CommunicationAgentService(
        send_notification_tool=fake_send,
        records_container=store,
        now_provider=lambda: now,
    )
    scheduler = EscalationScheduler(store, service, config=EscalationConfig())

    notifications = await scheduler.run_once(now=now)

    assert [item.albaran_id for item in notifications] == ["alb-reminder", "alb-escalated", "alb-expired"]
    assert [item.escalation_level for item in notifications] == [
        EscalationLevel.REMINDER_24H,
        EscalationLevel.ESCALATION_48H,
        EscalationLevel.FINAL_72H,
    ]
    assert [item["status"] for item in store.upserts] == ["reminded", "escalated", "expired"]
    assert len(sent_notifications) == 3
