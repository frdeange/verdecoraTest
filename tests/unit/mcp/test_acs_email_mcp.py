from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.mcp.acs_email_mcp.server import check_delivery_status, send_email, send_hitl_notification
from src.models.communication import EscalationLevel, HITLNotification


def test_send_email_builds_expected_acs_payload() -> None:
    poller = MagicMock()
    poller.result.return_value = {"id": "acs-msg-001", "status": "Succeeded"}
    client = SimpleNamespace(begin_send=MagicMock(return_value=poller))

    with (
        patch("src.mcp.acs_email_mcp.server.get_email_client", return_value=client),
        patch.dict(
            "os.environ",
            {"ACS_SENDER_ADDRESS": "DoNotReply@verdecora.example.com"},
            clear=False,
        ),
    ):
        result = send_email(
            to=["buyer@verdecora.example.com"],
            subject="Revisión requerida",
            body_html="<p>Hola</p>",
            reply_to="compras@verdecora.example.com",
        )

    message = client.begin_send.call_args.args[0]
    assert message["senderAddress"] == "DoNotReply@verdecora.example.com"
    assert message["recipients"]["to"][0]["address"] == "buyer@verdecora.example.com"
    assert message["replyTo"][0]["address"] == "compras@verdecora.example.com"
    assert result["message_id"] == "acs-msg-001"
    assert result["status"] == "Succeeded"


def test_send_hitl_notification_uses_notification_payload() -> None:
    notification = HITLNotification(
        albaran_id="alb-002",
        recipient_email="hitl@verdecora.example.com",
        subject="Asunto HITL",
        body_html="<p>Body</p>",
        escalation_level=EscalationLevel.INITIAL,
        callback_url="https://hitl.example.com/review/alb-002",
        pdf_sas_url="https://storage.example.com/alb-002.pdf",
        expires_at="2026-05-07T12:00:00Z",
    )

    with patch("src.mcp.acs_email_mcp.server.send_email", return_value={"message_id": "acs-msg-002"}) as mock_send:
        result = send_hitl_notification(notification)

    mock_send.assert_called_once_with(
        to="hitl@verdecora.example.com",
        subject="Asunto HITL",
        body_html="<p>Body</p>",
    )
    assert result == {"message_id": "acs-msg-002"}


def test_check_delivery_status_uses_client_method_when_available() -> None:
    client = SimpleNamespace(get_send_status=MagicMock(return_value={"status": "Delivered"}))

    with patch("src.mcp.acs_email_mcp.server.get_email_client", return_value=client):
        result = check_delivery_status("acs-msg-003")

    assert result["message_id"] == "acs-msg-003"
    assert result["status"] == "Delivered"
    assert result["delivered"] is True
