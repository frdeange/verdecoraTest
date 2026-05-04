from __future__ import annotations

import os
from functools import lru_cache
from urllib.parse import urlparse

from azure.identity import DefaultAzureCredential


class MCPServerError(Exception):
    """Base error for custom MCP server failures."""


class MCPConfigurationError(MCPServerError):
    """Raised when required configuration is missing."""


class MCPValidationError(MCPServerError):
    """Raised when a tool input cannot be processed."""


@lru_cache(maxsize=1)
def get_default_credential() -> DefaultAzureCredential:
    """Return the shared Azure credential used by custom MCP servers."""

    return DefaultAzureCredential(exclude_interactive_browser_credential=True)


def require_env(name: str) -> str:
    """Return a required environment variable or raise a configuration error."""

    value = os.getenv(name)
    if not value:
        raise MCPConfigurationError(f"Missing required environment variable: {name}")
    return value


def is_http_url(value: str) -> bool:
    """Return whether the provided value is an HTTP or HTTPS URL."""

    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
