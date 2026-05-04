from __future__ import annotations

import json
import os
import re
from html import unescape
from typing import Any, Callable
from urllib import request

from pydantic import BaseModel, Field

from src.config.security import get_managed_identity_credential

PROMPT_INJECTION_PATTERNS: dict[str, str] = {
    "ignore_previous_instructions": r"\b(?:ignore|disregard|forget)\b.{0,40}\b(?:previous|prior|above)\b.{0,40}\binstructions?\b",
    "reveal_system_prompt": r"\b(?:reveal|print|show|dump|expose)\b.{0,40}\b(?:system|hidden|developer)\b.{0,40}\bprompt\b",
    "override_role": r"\b(?:you are now|act as|pretend to be)\b",
    "jailbreak": r"\b(?:jailbreak|bypass|override|exfiltrate)\b",
    "script_injection": r"<\s*script\b",
    "tool_manipulation": r"\b(?:call_tool|function_call|tool:)\b",
}

LINE_STRIP_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        PROMPT_INJECTION_PATTERNS["ignore_previous_instructions"],
        PROMPT_INJECTION_PATTERNS["reveal_system_prompt"],
        PROMPT_INJECTION_PATTERNS["override_role"],
        PROMPT_INJECTION_PATTERNS["script_injection"],
    )
)


class AzureContentSafetyResult(BaseModel):
    blocked: bool = False
    attack_score: int = 0
    categories: dict[str, int] = Field(default_factory=dict)


class ContentSafetyAssessment(BaseModel):
    original_text: str
    sanitized_text: str
    matched_patterns: tuple[str, ...] = ()
    suspicious: bool = False
    azure_result: AzureContentSafetyResult | None = None


def detect_prompt_injection(text: str) -> tuple[str, ...]:
    normalized = normalize_text(text)
    matches = [
        name
        for name, pattern in PROMPT_INJECTION_PATTERNS.items()
        if re.search(pattern, normalized, flags=re.IGNORECASE)
    ]
    return tuple(matches)


def sanitize_ocr_text(text: str) -> str:
    normalized = normalize_text(text)
    normalized = re.sub(r"(?is)<script.*?>.*?</script>", " ", normalized)
    normalized = re.sub(r"(?is)```.*?```", " ", normalized)
    cleaned_lines: list[str] = []
    for raw_line in normalized.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if any(pattern.search(line) for pattern in LINE_STRIP_PATTERNS):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def normalize_text(text: str) -> str:
    return unescape(text.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")).strip()


class AzureContentSafetyClient:
    def __init__(
        self,
        endpoint: str | None = None,
        *,
        credential: Any | None = None,
        api_version: str = "2024-09-01",
        threshold: int = 1,
        http_post: Callable[[str, bytes, dict[str, str]], dict[str, Any]] | None = None,
    ) -> None:
        self.endpoint = (endpoint or os.getenv("AZURE_CONTENT_SAFETY_ENDPOINT", "")).rstrip("/")
        self.credential = credential or get_managed_identity_credential()
        self.api_version = api_version
        self.threshold = threshold
        self._http_post = http_post or self._default_http_post

    def analyze_text(self, text: str) -> AzureContentSafetyResult | None:
        if not self.endpoint:
            return None
        payload = json.dumps({"text": text}).encode("utf-8")
        response = self._http_post(
            f"{self.endpoint}/contentsafety/text:analyze?api-version={self.api_version}",
            payload,
            {
                "Authorization": f"Bearer {self._get_bearer_token()}",
                "Content-Type": "application/json",
            },
        )
        categories = {
            str(item.get("category") or "unknown"): int(item.get("severity") or 0)
            for item in response.get("categoriesAnalysis", [])
        }
        attack_score = max(categories.values(), default=0)
        blocked = bool(response.get("block", False)) or attack_score >= self.threshold
        return AzureContentSafetyResult(blocked=blocked, attack_score=attack_score, categories=categories)

    def _get_bearer_token(self) -> str:
        token = self.credential.get_token("https://cognitiveservices.azure.com/.default")
        return str(token.token)

    def _default_http_post(self, url: str, payload: bytes, headers: dict[str, str]) -> dict[str, Any]:
        http_request = request.Request(url=url, data=payload, headers=headers, method="POST")
        with request.urlopen(http_request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))


class OCRContentSafetyService:
    def __init__(self, azure_client: AzureContentSafetyClient | None = None) -> None:
        self.azure_client = azure_client or AzureContentSafetyClient()

    def assess_text(self, text: str) -> ContentSafetyAssessment:
        sanitized_text = sanitize_ocr_text(text)
        matched_patterns = detect_prompt_injection(text)
        azure_result = self.azure_client.analyze_text(sanitized_text)
        suspicious = bool(matched_patterns) or bool(azure_result and azure_result.blocked)
        return ContentSafetyAssessment(
            original_text=text,
            sanitized_text=sanitized_text,
            matched_patterns=matched_patterns,
            suspicious=suspicious,
            azure_result=azure_result,
        )


__all__ = [
    "AzureContentSafetyClient",
    "AzureContentSafetyResult",
    "ContentSafetyAssessment",
    "OCRContentSafetyService",
    "PROMPT_INJECTION_PATTERNS",
    "detect_prompt_injection",
    "sanitize_ocr_text",
]
