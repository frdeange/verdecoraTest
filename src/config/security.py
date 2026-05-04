from __future__ import annotations

from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def get_managed_identity_credential() -> Any:
    """Return the shared managed identity credential for Azure SDK clients."""

    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential(exclude_interactive_browser_credential=True)
