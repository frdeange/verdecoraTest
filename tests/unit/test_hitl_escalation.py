from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from src.agents.communication_agent import CommunicationAgentService
from src.models.communication import EscalationLevel
from src.services.escalation.config import EscalationConfig
from src.services.escalation.scheduler import CosmosEscalationStore, EscalationScheduler

pytestmark = pytest.mark.unit


class QueryCaptureContainer:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items
        self.query: str | None = None
        self.parameters: list[dict[str, Any]] | None = None

    async def query_items(self, *, query: str, parameters: list[dict[str, Any]]):
        self.query = query
        self.parameters = parameters
        for item in self.items:
            yield item


class QueryCaptureStore(CosmosEscalationStore):
    def __init__(self, config: EscalationConfig, container: QueryCaptureContainer) -> None:
        super().__init__(config)
        self._container = container

    async def _get_container(self) -> QueryCaptureContainer:
        return self._container


@pytest.mark.parametrize(
    ("hours_elapsed", "current_level", "expected_level"),
    [
        (25, EscalationLevel.INITIAL, EscalationLevel.REMINDER_24H),
        (49, EscalationLevel.REMINDER_24H, EscalationLevel.ESCALATION_48H),
        (73, EscalationLevel.ESCALATION_48H, EscalationLevel.FINAL_72H),
        (80, EscalationLevel.EXPIRED, None),
    ],
)
def test_escalation_level_transitions(
    hours_elapsed: int,
    current_level: EscalationLevel,
    expected_level: EscalationLevel | None,
) -> None:
    now = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)
    scheduler = EscalationScheduler(review_store=object(), communication_service=object(), config=EscalationConfig())

    next_level = scheduler.determine_next_level(
        {
            "id": "alb-escalation-001",
            "created_at": (now - timedelta(hours=hours_elapsed)).isoformat(),
            "escalation_level": current_level.value,
        },
        now=now,
    )

    assert next_level == expected_level


@pytest.mark.asyncio
async def test_scheduler_query_logic_lists_pending_reviews_in_created_order() -> None:
    container = QueryCaptureContainer(items=[{"id": "alb-001"}, {"id": "alb-002"}])
    store = QueryCaptureStore(EscalationConfig(query_batch_size=25), container)

    items = await store.list_pending_reviews()

    assert [item["id"] for item in items] == ["alb-001", "alb-002"]
    assert container.query is not None
    assert "c.status IN ('pending', 'reminded', 'escalated')" in container.query
    assert "ORDER BY c.created_at ASC" in container.query
    assert container.parameters == [{"name": "@limit", "value": 25}]


@pytest.mark.parametrize(
    ("level", "subject_fragment", "body_fragment"),
    [
        (EscalationLevel.REMINDER_24H, "Recordatorio de revisión pendiente", "intervención humana"),
        (EscalationLevel.ESCALATION_48H, "Escalado a responsable por demora", "Discrepancias detectadas"),
        (EscalationLevel.FINAL_72H, "Aviso final antes de expiración automática", "revise el formulario HITL"),
    ],
)
def test_notification_generation_for_reminder_escalation_and_final_notice(
    level: EscalationLevel,
    subject_fragment: str,
    body_fragment: str,
) -> None:
    service = CommunicationAgentService(now_provider=lambda: datetime(2026, 5, 5, 12, 0, tzinfo=UTC))
    review_record = {
        "id": "alb-hitl-002",
        "recipient_email": "manager@verdecora.example.com",
        "callback_url": "https://hitl.example.com/review/alb-hitl-002",
        "pdf_sas_url": "https://storage.example.com/alb-hitl-002.pdf?sig=abc",
        "pipeline_result": {
            "extraction": {"header": {"document_number": "ALB-HITL-002", "supplier_name": "Royal Canin"}},
            "validation": {"discrepancies": ["Precio fuera de tolerancia."]},
        },
    }

    notification = service.build_notification(review_record, escalation_level=level)

    assert subject_fragment in notification.subject
    assert body_fragment in notification.body_html
    assert notification.escalation_level is level
