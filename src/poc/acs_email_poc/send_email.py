from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from src.config.security import get_managed_identity_credential

from .email_templates import HitlEmailContext, render_hitl_email


@dataclass(slots=True)
class ACSMessageConfig:
    endpoint: str
    sender_address: str
    recipient_address: str
    sender_name: str = "Verdecora HITL"
    cc: tuple[str, ...] = field(default_factory=tuple)
    bcc: tuple[str, ...] = field(default_factory=tuple)
    reply_to: tuple[str, ...] = field(default_factory=tuple)
    credential: Any | None = None


def _create_email_client(config: ACSMessageConfig) -> Any:
    from azure.communication.email import EmailClient  # type: ignore[import-untyped]

    credential = config.credential or get_managed_identity_credential()
    return EmailClient(config.endpoint, credential)


def build_hitl_email_message(context: HitlEmailContext, config: ACSMessageConfig) -> dict[str, Any]:
    message: dict[str, Any] = {
        "content": {
            "subject": f"HITL review required · Albarán {context.albaran_number}",
            "plainText": (
                f"Discrepancy detected for albarán {context.albaran_number}. "
                f"Open the secure HITL form to accept, modify or reject."
            ),
            "html": render_hitl_email(context),
        },
        "recipients": {"to": [{"address": config.recipient_address, "displayName": "HITL Approver"}]},
        "senderAddress": config.sender_address,
    }

    if config.cc:
        message["recipients"]["cc"] = [{"address": address} for address in config.cc]
    if config.bcc:
        message["recipients"]["bcc"] = [{"address": address} for address in config.bcc]
    if config.reply_to:
        message["replyTo"] = [{"address": address} for address in config.reply_to]
    if config.sender_name:
        message["senderDisplayName"] = config.sender_name

    return message


def _extract_message_id(send_result: Any, poller: Any) -> str:
    candidates: Iterable[Any] = (send_result, getattr(poller, "result", None), getattr(poller, "details", None))
    for candidate in candidates:
        if candidate is None:
            continue
        if isinstance(candidate, Mapping):
            for key in ("id", "message_id", "messageId"):
                if candidate.get(key):
                    return str(candidate[key])
        for attribute in ("id", "message_id", "messageId"):
            value = getattr(candidate, attribute, None)
            if value:
                return str(value)
    raise RuntimeError("ACS Email send completed but no message_id could be extracted from the SDK response.")


def send_hitl_email(context: HitlEmailContext, config: ACSMessageConfig, client: Any | None = None) -> str:
    """Send the HITL email through Azure Communication Services Email and return its message id."""

    email_client = client or _create_email_client(config)
    message = build_hitl_email_message(context, config)
    poller = email_client.begin_send(message)
    send_result = poller.result()
    return _extract_message_id(send_result, poller)
