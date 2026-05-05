from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import TypeAdapter

from src.models.store import Store

_STORE_LIST_ADAPTER = TypeAdapter(list[Store])
_STORE_CATALOG_PATH = Path(__file__).resolve().parents[3] / "data" / "stores" / "verdecora-stores.json"


@lru_cache(maxsize=1)
def load_stores() -> list[Store]:
    """Load and cache the shared Verdecora store catalog."""

    payload = json.loads(_STORE_CATALOG_PATH.read_text(encoding="utf-8"))
    return _STORE_LIST_ADAPTER.validate_python(payload)
