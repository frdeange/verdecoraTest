"""Integration tests for Flow0 multipage/session-based grouping."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from src.services.flow0_dedup.dedup_handler import Flow0DedupHandler

pytestmark = pytest.mark.integration


class FakeCosmosContainer:
    """In-memory Cosmos container for testing."""

    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def upsert_item(self, *, body: dict[str, Any]) -> dict[str, Any]:
        self.items[str(body["id"])] = dict(body)
        return dict(body)

    def query_items(self, *, parameters: list[dict[str, Any]], **_: Any) -> list[dict[str, Any]]:
        param_map = {p["name"]: p["value"] for p in parameters}
        dedup_key = param_map.get("@dedup_key")
        matches = [item for item in self.items.values() if item.get("dedup_key") == dedup_key]
        return matches[:1]


class FakeSender:
    """Collects Service Bus messages in-memory."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def send_messages(self, message: Any) -> None:
        body = b"".join(bytes(part) for part in message.body)
        self.messages.append(json.loads(body.decode("utf-8")))


def _build_session_payload(
    session_id: str = "sess-multi-001",
    user_oid: str = "oid-user-001",
    files: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if files is None:
        files = []
    return {
        "session_id": session_id,
        "user_oid": user_oid,
        "files": files,
        "confirmed_at": datetime.now(UTC).isoformat(),
    }


@pytest.mark.integration
def test_three_files_one_group_single_record() -> None:
    """3 files in 1 albaran group → processed as single multi-page document."""
    container = FakeCosmosContainer()
    sender = FakeSender()
    handler = Flow0DedupHandler(container, sender)

    payload = _build_session_payload(
        files=[
            {"filename": "page1.pdf", "blob_path": "sess-multi-001/page1.pdf", "albaran_group": "alb-A"},
            {"filename": "page2.pdf", "blob_path": "sess-multi-001/page2.pdf", "albaran_group": "alb-A"},
            {"filename": "page3.pdf", "blob_path": "sess-multi-001/page3.pdf", "albaran_group": "alb-A"},
        ]
    )

    records = handler.handle_session_message(payload)

    assert len(records) == 1
    assert records[0].upload_session_id == "sess-multi-001"
    assert records[0].uploader_oid == "oid-user-001"
    assert records[0].source_metadata["page_count"] == 3
    assert len(records[0].source_metadata["blob_paths"]) == 3
    assert len(container.items) == 1
    assert len(sender.messages) == 1
    assert sender.messages[0]["albaran_group"] == "alb-A"


@pytest.mark.integration
def test_two_groups_two_records() -> None:
    """2 albaran groups in 1 session → 2 separate processing jobs."""
    container = FakeCosmosContainer()
    sender = FakeSender()
    handler = Flow0DedupHandler(container, sender)

    payload = _build_session_payload(
        session_id="sess-multi-002",
        files=[
            {"filename": "a1.pdf", "blob_path": "sess-multi-002/a1.pdf", "albaran_group": "group-X"},
            {"filename": "a2.pdf", "blob_path": "sess-multi-002/a2.pdf", "albaran_group": "group-X"},
            {"filename": "b1.pdf", "blob_path": "sess-multi-002/b1.pdf", "albaran_group": "group-Y"},
        ],
    )

    records = handler.handle_session_message(payload)

    assert len(records) == 2
    assert len(container.items) == 2
    assert len(sender.messages) == 2

    groups_seen = {msg["albaran_group"] for msg in sender.messages}
    assert groups_seen == {"group-X", "group-Y"}

    # Verify group-X has 2 pages and group-Y has 1
    for record in records:
        if record.source_metadata["albaran_group"] == "group-X":
            assert record.source_metadata["page_count"] == 2
        else:
            assert record.source_metadata["page_count"] == 1


@pytest.mark.integration
def test_dedup_handles_reupload_within_session() -> None:
    """Re-uploading the same session produces new records with same dedup keys."""
    container = FakeCosmosContainer()
    sender = FakeSender()
    handler = Flow0DedupHandler(container, sender)

    payload = _build_session_payload(
        session_id="sess-reupload",
        files=[
            {"filename": "doc.pdf", "blob_path": "sess-reupload/doc.pdf", "albaran_group": "g1"},
        ],
    )

    # First submission
    records1 = handler.handle_session_message(payload)
    assert len(records1) == 1
    first_id = records1[0].id

    # Second submission (re-upload) - same session_id + group = same dedup_key = same record ID
    records2 = handler.handle_session_message(payload)
    assert len(records2) == 1
    assert records2[0].id == first_id  # Same dedup key → same record ID

    # Cosmos should have 1 item (upsert overwrites)
    assert len(container.items) == 1
    # But sender received 2 messages (one per call)
    assert len(sender.messages) == 2


@pytest.mark.integration
def test_files_without_group_default_group() -> None:
    """Files with no albaran_group use 'default' as the group key."""
    container = FakeCosmosContainer()
    sender = FakeSender()
    handler = Flow0DedupHandler(container, sender)

    payload = _build_session_payload(
        session_id="sess-no-group",
        files=[
            {"filename": "a.pdf", "blob_path": "sess-no-group/a.pdf"},
            {"filename": "b.pdf", "blob_path": "sess-no-group/b.pdf"},
        ],
    )

    records = handler.handle_session_message(payload)

    assert len(records) == 1
    assert records[0].source_metadata["albaran_group"] == "default"
    assert records[0].source_metadata["page_count"] == 2
    assert sender.messages[0]["albaran_group"] == "default"
