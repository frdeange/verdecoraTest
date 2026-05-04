from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

from src.services.flow0_dedup.models import EventGridEnvelope, ForwardedExtractionMessage, ProcessingRecord

LOGGER = logging.getLogger(__name__)


def parse_event_grid_payload(payload: str | bytes | bytearray | dict[str, Any] | list[Any]) -> EventGridEnvelope:
    """Parse a Service Bus payload that carries an Event Grid BlobCreated event."""

    raw_payload: Any = payload
    if isinstance(raw_payload, (bytes, bytearray)):
        raw_payload = raw_payload.decode("utf-8")
    if isinstance(raw_payload, str):
        raw_payload = json.loads(raw_payload)
    if isinstance(raw_payload, list):
        if not raw_payload:
            raise ValueError("Event Grid payload list is empty")
        raw_payload = raw_payload[0]
    if not isinstance(raw_payload, dict):
        raise TypeError("Event Grid payload must decode to a dict or non-empty list")
    return EventGridEnvelope.model_validate(raw_payload)


def extract_store_id(blob_path: str) -> str:
    """Return the tienda/store identifier embedded in the blob path."""

    segments = [segment for segment in blob_path.split("/") if segment]
    return segments[3] if len(segments) >= 4 else "unknown-store"


def build_partition_key(store_id: str, event_time: datetime) -> str:
    """Build the Cosmos partition key expected by the albaranes container."""

    return f"{store_id}_{event_time:%Y_%m}"


def build_dedup_key(event: EventGridEnvelope) -> str:
    """Build the deduplication key using blob hash/etag or name+date fallback."""

    if event.data.blob_hash:
        return f"hash:{event.data.blob_hash}"
    if event.data.eTag:
        return f"etag:{event.data.eTag}"
    return f"name-date:{event.blob_name}:{event.eventTime.date().isoformat()}"


class Flow0DedupHandler:
    """Encapsulates the Cosmos-backed deduplication and queue forwarding logic."""

    def __init__(self, container_client: Any, sender: Any, logger: logging.Logger | None = None) -> None:
        self._container_client = container_client
        self._sender = sender
        self._logger = logger or LOGGER

    def find_existing_record(self, event: EventGridEnvelope, dedup_key: str) -> dict[str, Any] | None:
        """Return an existing processing record when the blob was already seen."""

        parameters = [
            {"name": "@dedup_key", "value": dedup_key},
            {"name": "@blob_name", "value": event.blob_name},
            {"name": "@event_date", "value": event.eventTime.date().isoformat()},
        ]
        query = (
            "SELECT TOP 1 c.id, c.status, c.dedup_key "
            "FROM c WHERE c.dedup_key = @dedup_key "
            "OR (c.blob_name = @blob_name AND c.event_date = @event_date)"
        )
        items = list(
            self._container_client.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
            )
        )
        return dict(items[0]) if items else None

    def build_processing_record(self, event: EventGridEnvelope) -> ProcessingRecord:
        """Build the Cosmos processing record for a newly ingested blob."""

        store_id = extract_store_id(event.blob_path)
        dedup_key = build_dedup_key(event)
        record_id = f"albaran-{hashlib.sha256(dedup_key.encode('utf-8')).hexdigest()[:24]}"
        return ProcessingRecord(
            id=record_id,
            pk=build_partition_key(store_id, event.eventTime),
            store_id=store_id,
            event_id=event.id,
            event_type=event.eventType,
            event_time=event.eventTime,
            event_date=event.eventTime.date().isoformat(),
            dedup_key=dedup_key,
            blob_url=event.blob_url,
            blob_path=event.blob_path,
            blob_name=event.blob_name,
            blob_etag=event.data.eTag,
            source_metadata={
                "subject": event.subject,
                "topic": event.topic,
                "content_type": event.data.contentType,
                "content_length": event.data.contentLength,
                "storage_diagnostics": event.data.storageDiagnostics,
                "blob_metadata": event.data.metadata,
            },
        )

    def build_forward_message(self, record: ProcessingRecord) -> ForwardedExtractionMessage:
        """Build the message forwarded to the extraction queue."""

        return ForwardedExtractionMessage(
            albaran_id=record.id,
            dedup_key=record.dedup_key,
            blob_url=record.blob_url,
            blob_path=record.blob_path,
            blob_name=record.blob_name,
            blob_etag=record.blob_etag,
            store_id=record.store_id,
            event_id=record.event_id,
            event_time=record.event_time,
            metadata=record.source_metadata,
        )

    def forward_to_extraction_queue(self, record: ProcessingRecord) -> None:
        """Send the normalized message into the extraction queue."""

        from azure.servicebus import ServiceBusMessage

        outbound = self.build_forward_message(record)
        message = ServiceBusMessage(
            json.dumps(outbound.model_dump(mode="json")),
            application_properties={"eventType": "albaran.recibido"},
            subject="albaran.recibido",
        )
        self._sender.send_messages(message)

    def handle_message(self, payload: str | bytes | bytearray | dict[str, Any] | list[Any]) -> bool:
        """Process one message and return whether it was forwarded downstream."""

        event = parse_event_grid_payload(payload)
        dedup_key = build_dedup_key(event)
        existing = self.find_existing_record(event, dedup_key)
        if existing:
            self._logger.info(
                "Duplicate blob skipped",
                extra={"dedup_key": dedup_key, "existing_id": existing.get("id"), "blob_name": event.blob_name},
            )
            return False

        record = self.build_processing_record(event)
        self._container_client.upsert_item(body=record.model_dump(mode="json"))
        self.forward_to_extraction_queue(record)
        self._logger.info(
            "Flow 0 record created and forwarded",
            extra={"albaran_id": record.id, "dedup_key": record.dedup_key, "blob_name": record.blob_name},
        )
        return True
