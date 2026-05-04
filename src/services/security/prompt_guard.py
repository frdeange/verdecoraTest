from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from .content_safety import OCRContentSafetyService

LOGGER = logging.getLogger("security.prompt_guard")


class PromptGuardViolation(ValueError):
    """Raised when an LLM input contains prompt-injection signals or unsafe content."""


class GuardedPrompt(BaseModel):
    sanitized_text: str
    suspicious: bool
    matched_patterns: tuple[str, ...] = ()


class PromptGuard:
    def __init__(
        self,
        content_safety_service: OCRContentSafetyService | None = None,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self.content_safety_service = content_safety_service or OCRContentSafetyService()
        self.logger = logger or LOGGER

    def validate_text(self, text: str) -> GuardedPrompt:
        assessment = self.content_safety_service.assess_text(text)
        if assessment.suspicious:
            self.logger.warning(
                "Blocked suspicious LLM input",
                extra={"matched_patterns": assessment.matched_patterns},
            )
            raise PromptGuardViolation(
                "Blocked suspicious LLM input: "
                + ", ".join(assessment.matched_patterns or ("azure_content_safety",))
            )
        return GuardedPrompt(
            sanitized_text=assessment.sanitized_text,
            suspicious=assessment.suspicious,
            matched_patterns=assessment.matched_patterns,
        )

    def validate_payload(self, payload: Any) -> Any:
        return self._sanitize_value(payload)

    def _sanitize_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.validate_text(value).sanitized_text
        if isinstance(value, Mapping):
            return {str(key): self._sanitize_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._sanitize_value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._sanitize_value(item) for item in value)
        return value


__all__ = ["GuardedPrompt", "PromptGuard", "PromptGuardViolation"]
