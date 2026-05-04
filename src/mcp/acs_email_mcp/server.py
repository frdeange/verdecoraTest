from __future__ import annotations

from functools import lru_cache
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.mcp.common import MCPValidationError, get_default_credential, require_env
from src.models.communication import HITLNotification

from .models import DeliveryStatus, EmailResult

mcp = FastMCP("verdecora-acs-email-mcp", json_response=True)


@lru_cache(maxsize=1)
def get_email_client() -> Any:
    try:
        from azure.communication.email import EmailClient
    except ModuleNotFoundError as exc:  # pragma: no cover - optional runtime dependency.
        raise RuntimeError("azure-communication-email is required to send ACS emails.") from exc

    return EmailClient(endpoint=require_env("ACS_ENDPOINT"), credential=get_default_credential())


def _get_sender_address() -> str:
    return require_env("ACS_SENDER_ADDRESS")


def _normalize_recipients(to: str | list[str]) -> list[str]:
    recipients = [to] if isinstance(to, str) else list(to)
    normalized = [candidate.strip() for candidate in recipients if candidate and candidate.strip()]
    if not normalized:
        raise MCPValidationError("At least one recipient email is required.")
    return normalized


def _extract_message_id(send_result: Any, poller: Any) -> str:
    candidates = (send_result, getattr(poller, "result", None), getattr(poller, "details", None))
    for candidate in candidates:
        if candidate is None:
            continue
        if isinstance(candidate, dict):
            for key in ("id", "message_id", "messageId"):
                value = candidate.get(key)
                if value:
                    return str(value)
        for attribute in ("id", "message_id", "messageId"):
            value = getattr(candidate, attribute, None)
            if value:
                return str(value)
    raise RuntimeError("ACS Email send completed but no message identifier was returned.")


def _extract_status(payload: Any, *, default: str) -> str:
    if isinstance(payload, dict):
        return str(payload.get("status") or payload.get("deliveryStatus") or default)
    for attribute in ("status", "delivery_status", "deliveryStatus"):
        value = getattr(payload, attribute, None)
        if value:
            return str(value)
    return default


def _build_message(
    *, recipients: list[str], subject: str, body_html: str, reply_to: str | None = None
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "content": {"subject": subject, "html": body_html},
        "recipients": {"to": [{"address": recipient} for recipient in recipients]},
        "senderAddress": _get_sender_address(),
    }
    if reply_to and reply_to.strip():
        message["replyTo"] = [{"address": reply_to.strip()}]
    return message


@mcp.tool()
def send_email(to: str | list[str], subject: str, body_html: str, reply_to: str | None = None) -> dict[str, Any]:
    recipients = _normalize_recipients(to)
    message = _build_message(recipients=recipients, subject=subject, body_html=body_html, reply_to=reply_to)
    poller = get_email_client().begin_send(message)
    send_result = poller.result()
    result = EmailResult(
        message_id=_extract_message_id(send_result, poller),
        status=_extract_status(send_result, default="queued"),
        recipients=recipients,
        subject=subject,
        details=send_result if isinstance(send_result, dict) else {},
    )
    return result.model_dump(mode="json")


@mcp.tool()
def send_hitl_notification(notification: HITLNotification) -> dict[str, Any]:
    return send_email(
        to=notification.recipient_email,
        subject=notification.subject,
        body_html=notification.body_html,
    )


@mcp.tool()
def check_delivery_status(message_id: str) -> dict[str, Any]:
    if not message_id.strip():
        raise MCPValidationError("message_id must not be empty")
    client = get_email_client()
    for attribute in ("get_send_status", "get_delivery_status", "get_message_status"):
        status_getter = getattr(client, attribute, None)
        if callable(status_getter):
            status_result = status_getter(message_id)
            status = DeliveryStatus(
                message_id=message_id,
                status=_extract_status(status_result, default="unknown"),
                delivered=_extract_status(status_result, default="unknown").casefold() in {"delivered", "succeeded"},
                details=status_result if isinstance(status_result, dict) else {},
            )
            return status.model_dump(mode="json")
    return DeliveryStatus(
        message_id=message_id,
        status="unknown",
        delivered=False,
        details={"message": "The current ACS Email SDK client does not expose a delivery-status polling method."},
    ).model_dump(mode="json")


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
