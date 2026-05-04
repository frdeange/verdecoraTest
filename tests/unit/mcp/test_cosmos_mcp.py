from __future__ import annotations

import pytest

from src.mcp.common import MCPValidationError
from src.mcp.cosmos_mcp.server import upsert_document


def test_upsert_document_requires_id() -> None:
    with pytest.raises(MCPValidationError):
        upsert_document("db", "container", {"pk": "abc"})
