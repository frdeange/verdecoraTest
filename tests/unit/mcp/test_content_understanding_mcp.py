from __future__ import annotations

import base64

import pytest

from src.mcp.common import MCPValidationError
from src.mcp.content_understanding_mcp.server import build_analyze_request


def test_build_analyze_request_accepts_https_url() -> None:
    request = build_analyze_request("https://example.com/document.pdf")

    assert request.url_source == "https://example.com/document.pdf"
    assert request.bytes_source is None


def test_build_analyze_request_accepts_base64_payload() -> None:
    payload = base64.b64encode(b"hello world").decode("utf-8")

    request = build_analyze_request(payload)

    assert request.url_source is None
    assert request.bytes_source == b"hello world"


def test_build_analyze_request_rejects_invalid_input() -> None:
    with pytest.raises(MCPValidationError):
        build_analyze_request("not-a-url-or-base64")
