from __future__ import annotations

import sys
from datetime import date
from types import SimpleNamespace

from src.poc.acs_email_poc.email_templates import HitlEmailContext
from src.poc.acs_email_poc.send_email import ACSMessageConfig, _create_email_client, send_hitl_email


def _build_config(**overrides: object) -> ACSMessageConfig:
    values: dict[str, object] = {
        "endpoint": "https://example.communication.azure.com",
        "sender_address": "DoNotReply@verdecora.example.com",
        "recipient_address": "responsable.principal@verdecora.example.com",
    }
    values.update(overrides)
    return ACSMessageConfig(**values)


def test_create_email_client_uses_supplied_credential(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeEmailClient:
        def __init__(self, endpoint: str, credential: object) -> None:
            captured["endpoint"] = endpoint
            captured["credential"] = credential

    monkeypatch.setitem(sys.modules, "azure.communication.email", SimpleNamespace(EmailClient=FakeEmailClient))

    credential = object()
    client = _create_email_client(_build_config(credential=credential))

    assert isinstance(client, FakeEmailClient)
    assert captured == {
        "endpoint": "https://example.communication.azure.com",
        "credential": credential,
    }


def test_create_email_client_uses_managed_identity_when_credential_missing(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeEmailClient:
        def __init__(self, endpoint: str, credential: object) -> None:
            captured["endpoint"] = endpoint
            captured["credential"] = credential

    monkeypatch.setitem(sys.modules, "azure.communication.email", SimpleNamespace(EmailClient=FakeEmailClient))

    managed_identity_credential = object()
    monkeypatch.setattr(
        "src.poc.acs_email_poc.send_email.get_managed_identity_credential",
        lambda: managed_identity_credential,
    )

    _create_email_client(_build_config())

    assert captured == {
        "endpoint": "https://example.communication.azure.com",
        "credential": managed_identity_credential,
    }


def test_send_hitl_email_returns_message_id(acs_email_client) -> None:
    context = HitlEmailContext(
        albaran_id="hitl-001",
        albaran_number="ALB-2026-00142",
        supplier_name="Viveros El Pino S.L.",
        delivery_date=date(2026, 5, 4),
        po_reference="PO-2026-003201",
        pdf_url="https://example.com/albaran.pdf",
        token="secure-token",
    )
    config = _build_config()

    message_id = send_hitl_email(context, config, client=acs_email_client)

    assert message_id == "acs-msg-001"
