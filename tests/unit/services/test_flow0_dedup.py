from __future__ import annotations

from src.services.flow0_dedup.dedup_handler import build_dedup_key, build_partition_key, parse_event_grid_payload


def test_parse_event_grid_payload_accepts_event_grid_arrays() -> None:
    event = parse_event_grid_payload(
        [
            {
                "id": "evt-1",
                "eventType": "Microsoft.Storage.BlobCreated",
                "subject": "/blobServices/default/containers/albaranes-raw/blobs/2026/05/tienda_007/test.pdf",
                "eventTime": "2026-05-04T08:12:33Z",
                "data": {
                    "eTag": "etag-1",
                    "url": "https://storage.blob.core.windows.net/albaranes-raw/2026/05/tienda_007/test.pdf",
                    "metadata": {"blob_hash": "abc123"},
                },
            }
        ]
    )

    assert event.id == "evt-1"
    assert event.blob_path == "albaranes-raw/2026/05/tienda_007/test.pdf"
    assert event.blob_name == "test.pdf"


def test_build_dedup_key_prefers_hash_then_etag_then_name_and_date() -> None:
    event = parse_event_grid_payload(
        {
            "id": "evt-2",
            "eventType": "Microsoft.Storage.BlobCreated",
            "subject": "/blobServices/default/containers/albaranes-raw/blobs/2026/05/tienda_007/test.pdf",
            "eventTime": "2026-05-04T08:12:33Z",
            "data": {
                "eTag": "etag-2",
                "url": "https://storage.blob.core.windows.net/albaranes-raw/2026/05/tienda_007/test.pdf",
                "metadata": {"blob_hash": "hash-2"},
            },
        }
    )
    assert build_dedup_key(event) == "hash:hash-2"

    event_without_hash = event.model_copy(update={"data": event.data.model_copy(update={"metadata": {}})})
    assert build_dedup_key(event_without_hash) == "etag:etag-2"

    event_without_etag = event_without_hash.model_copy(update={"data": event.data.model_copy(update={"metadata": {}, "eTag": None})})
    assert build_dedup_key(event_without_etag) == "name-date:test.pdf:2026-05-04"


def test_build_partition_key_uses_store_and_year_month() -> None:
    event = parse_event_grid_payload(
        {
            "id": "evt-3",
            "eventType": "Microsoft.Storage.BlobCreated",
            "subject": "/blobServices/default/containers/albaranes-raw/blobs/2026/05/tienda_001/test.pdf",
            "eventTime": "2026-05-04T08:12:33Z",
            "data": {"url": "https://storage.blob.core.windows.net/albaranes-raw/2026/05/tienda_001/test.pdf"},
        }
    )

    assert build_partition_key("tienda_001", event.eventTime) == "tienda_001_2026_05"
