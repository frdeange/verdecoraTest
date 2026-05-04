from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field


class RedactionRule(BaseModel):
    name: str
    pattern: str
    replacement: str


class PIIRedactorConfig(BaseModel):
    driver_fields: tuple[str, ...] = ("transportista", "driver_name", "driver", "nombre_transportista")
    signature_fields: tuple[str, ...] = ("signature", "signature_region", "firma", "firma_region")
    signature_placeholder: str = "[SIGNATURE REDACTED]"
    driver_placeholder: str = "[DRIVER NAME REDACTED]"
    field_replacements: dict[str, str] = Field(default_factory=dict)
    custom_rules: tuple[RedactionRule, ...] = ()


class PIIRedactor:
    _DEFAULT_RULES: tuple[RedactionRule, ...] = (
        RedactionRule(
            name="email",
            pattern=r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
            replacement="[EMAIL REDACTED]",
        ),
        RedactionRule(
            name="phone",
            pattern=r"\b(?:\+34\s?)?(?:\d[\s-]?){9,12}\b",
            replacement="[PHONE REDACTED]",
        ),
        RedactionRule(
            name="personal_id",
            pattern=r"\b(?:\d{8}[A-Z]|[XYZ]\d{7}[A-Z]|[A-Z]{2}\d{6})\b",
            replacement="[PERSONAL ID REDACTED]",
        ),
    )

    def __init__(self, config: PIIRedactorConfig | None = None) -> None:
        self.config = config or PIIRedactorConfig()
        self._compiled_rules = [
            (re.compile(rule.pattern, re.IGNORECASE), rule.replacement)
            for rule in (*self._DEFAULT_RULES, *self.config.custom_rules)
        ]

    def redact_text(self, text: str) -> str:
        redacted = text
        for pattern, replacement in self._compiled_rules:
            redacted = pattern.sub(replacement, redacted)
        return redacted

    def redact_pdf_text(self, text: str) -> str:
        redacted = self.redact_text(text)
        redacted = re.sub(
            r"(?is)\[signature\].*?\[/signature\]",
            self.config.signature_placeholder,
            redacted,
        )
        redacted = re.sub(
            r"(?im)^(?:firma|signature)\s*:.*$",
            self.config.signature_placeholder,
            redacted,
        )
        return redacted

    def redact_record(self, record: Mapping[str, Any]) -> dict[str, Any]:
        return {str(key): self._redact_value(str(key), value) for key, value in record.items()}

    def _redact_value(self, field_name: str, value: Any) -> Any:
        normalized_field = field_name.casefold()
        if isinstance(value, Mapping):
            return self.redact_record(value)
        if isinstance(value, list):
            return [self._redact_value(field_name, item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._redact_value(field_name, item) for item in value)
        if not isinstance(value, str):
            return value
        if normalized_field in {item.casefold() for item in self.config.driver_fields}:
            return self.config.field_replacements.get(normalized_field, self.config.driver_placeholder)
        if normalized_field in {item.casefold() for item in self.config.signature_fields}:
            return self.config.field_replacements.get(normalized_field, self.config.signature_placeholder)
        return self.redact_text(value)


__all__ = ["PIIRedactor", "PIIRedactorConfig", "RedactionRule"]
