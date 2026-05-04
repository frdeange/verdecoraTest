from __future__ import annotations

import pytest

from src.services.security.pii_redactor import PIIRedactor, PIIRedactorConfig

pytestmark = pytest.mark.unit


def test_redact_record_masks_transportista_name() -> None:
    redactor = PIIRedactor()

    redacted = redactor.redact_record({"transportista": "Juan Pérez", "status": "ok"})

    assert redacted["transportista"] == "[DRIVER NAME REDACTED]"
    assert redacted["status"] == "ok"


def test_redact_pdf_text_replaces_signature_regions() -> None:
    redactor = PIIRedactor()

    redacted = redactor.redact_pdf_text("Entrega validada\nFirma: Juan Pérez\n[signature]trace[/signature]")

    assert redacted.count("[SIGNATURE REDACTED]") == 2


@pytest.mark.parametrize(
    ("text", "replacement"),
    [
        ("Contacto: maria@verdecora.es", "[EMAIL REDACTED]"),
        ("Teléfono: +34 600 123 123", "[PHONE REDACTED]"),
        ("DNI: 12345678Z", "[PERSONAL ID REDACTED]"),
    ],
)
def test_redact_text_masks_common_pii(text: str, replacement: str) -> None:
    redactor = PIIRedactor()

    redacted = redactor.redact_text(text)

    assert replacement in redacted


def test_field_specific_replacements_are_configurable() -> None:
    redactor = PIIRedactor(
        PIIRedactorConfig(field_replacements={"transportista": "[CUSTOM DRIVER REDACTION]"})
    )

    redacted = redactor.redact_record({"transportista": "Juan Pérez"})

    assert redacted["transportista"] == "[CUSTOM DRIVER REDACTION]"
