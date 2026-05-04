from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest

from src.agents.communication_agent import CommunicationAgentService, CommunicationSummary, create_communication_agent
from src.config.agents import AgentsConfig
from src.models.communication import EscalationLevel
from tests.unit.agent_test_helpers import StructuredAgentStub, build_structured_agent_stub

pytestmark = pytest.mark.unit


class FakeRecordStore:
    def __init__(self) -> None:
        self.upserts: list[dict[str, Any]] = []

    async def upsert_item(self, document: dict[str, Any]) -> dict[str, Any]:
        self.upserts.append(document)
        return document


@patch("src.agents.communication_agent.create_structured_agent", side_effect=build_structured_agent_stub)
def test_create_communication_agent_uses_expected_model_and_prompt(mock_factory: Any) -> None:
    agent = create_communication_agent(client=object(), tools=["acs.send_hitl_notification"])

    assert isinstance(agent, StructuredAgentStub)
    kwargs = mock_factory.call_args.kwargs
    assert kwargs["name"] == "a6-communication"
    assert kwargs["model"] == "gpt-5-mini"
    assert kwargs["structured_output"] is CommunicationSummary
    assert kwargs["tools"] == ["acs.send_hitl_notification"]
    assert "español" in kwargs["instructions"]


@patch("src.agents.communication_agent.create_structured_agent", side_effect=build_structured_agent_stub)
def test_create_communication_agent_respects_custom_model_config(mock_factory: Any) -> None:
    config = AgentsConfig.model_validate({"models": {"communication_model": "communication-local"}})

    create_communication_agent(client=object(), config=config)

    assert mock_factory.call_args.kwargs["model"] == "communication-local"


@pytest.mark.asyncio
async def test_communication_agent_service_builds_notification_and_tracks_cosmos_state() -> None:
    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    store = FakeRecordStore()
    sent_notifications = []

    def fake_send(notification: Any) -> dict[str, str]:
        sent_notifications.append(notification)
        return {"message_id": "acs-msg-001", "status": "queued"}

    service = CommunicationAgentService(
        send_notification_tool=fake_send,
        records_container=store,
        now_provider=lambda: now,
    )
    review_record = {
        "id": "alb-001",
        "recipient_email": "compras@verdecora.example.com",
        "callback_url": "https://hitl.example.com/review/alb-001",
        "pdf_sas_url": "https://storage.example.com/alb-001.pdf?sig=abc",
        "expires_at": (now + timedelta(hours=36)).isoformat(),
        "pipeline_result": {
            "extraction": {"header": {"document_number": "ALB-001", "supplier_name": "Herstera Garden"}},
            "validation": {"discrepancies": ["Cantidad distinta en la línea 2."]},
        },
    }

    notification = await service.handle_hitl_review(review_record, escalation_level=EscalationLevel.REMINDER_24H)

    assert notification.albaran_id == "alb-001"
    assert notification.recipient_email == "compras@verdecora.example.com"
    assert notification.escalation_level is EscalationLevel.REMINDER_24H
    assert "Cantidad distinta" in notification.body_html
    assert sent_notifications == [notification]
    assert store.upserts[0]["status"] == "reminded"
    assert store.upserts[0]["escalation_level"] == EscalationLevel.REMINDER_24H.value
