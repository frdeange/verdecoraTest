from __future__ import annotations

import asyncio
import json
from typing import Any

from src.services.flow0_dedup.models import ForwardedExtractionMessage

from .orchestration import OrchestrationError, OrchestrationRequest, OrchestrationResult, OrchestratorService


class QueueMessageError(ValueError):
    """Raised when a Service Bus payload cannot be converted into an orchestration request."""


def deserialize_message(message: Any) -> OrchestrationRequest:
    if hasattr(message, "body"):
        body = b"".join(bytes(part) for part in message.body)
    else:
        body = message

    if isinstance(body, bytes):
        payload: Any = json.loads(body.decode("utf-8"))
    elif isinstance(body, str):
        payload = json.loads(body)
    else:
        payload = body

    if isinstance(payload, dict) and "albaran_id" in payload:
        try:
            forwarded = ForwardedExtractionMessage.model_validate(payload)
        except Exception as exc:  # pragma: no cover - defensive parsing path.
            raise QueueMessageError("Invalid Service Bus payload for orchestration.") from exc
    else:
        try:
            return OrchestrationRequest.model_validate(payload)
        except Exception:
            try:
                forwarded = ForwardedExtractionMessage.model_validate(payload)
            except Exception as exc:  # pragma: no cover - defensive parsing path.
                raise QueueMessageError("Invalid Service Bus payload for orchestration.") from exc

    metadata = dict(forwarded.metadata)
    metadata.update(
        {
            "dedup_key": forwarded.dedup_key,
            "blob_path": forwarded.blob_path,
            "blob_name": forwarded.blob_name,
            "blob_etag": forwarded.blob_etag,
            "store_id": forwarded.store_id,
            "event_id": forwarded.event_id,
            "event_time": forwarded.event_time.isoformat(),
        }
    )
    return OrchestrationRequest(
        processing_id=forwarded.albaran_id,
        blob_url=forwarded.blob_url,
        metadata=metadata,
    )


async def handle_message(
    orchestrator: OrchestratorService,
    *,
    receiver: Any,
    message: Any,
) -> OrchestrationResult:
    request = deserialize_message(message)
    try:
        result = await orchestrator.process_document(request)
    except OrchestrationError as exc:
        if getattr(message, "delivery_count", 1) >= orchestrator.config.max_delivery_attempts:
            await receiver.dead_letter_message(
                message,
                reason="orchestration_failed",
                error_description=str(exc),
            )
        else:
            await receiver.abandon_message(message)
        return exc.result

    await receiver.complete_message(message)
    return result


async def consume_extraction_queue(orchestrator: OrchestratorService, *, max_wait_time: int = 5) -> int:
    service_bus_client = orchestrator.dependencies.get_service_bus_client()
    async with service_bus_client.get_queue_receiver(queue_name=orchestrator.config.extraction_queue_name) as receiver:
        messages = await receiver.receive_messages(
            max_message_count=orchestrator.config.max_receive_batch_size,
            max_wait_time=max_wait_time,
        )
        for message in messages:
            await handle_message(orchestrator, receiver=receiver, message=message)
        return len(messages)


async def run_queue_consumer(orchestrator: OrchestratorService, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        received = await consume_extraction_queue(orchestrator)
        if received > 0:
            continue
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=orchestrator.config.service_bus_poll_interval_seconds)
        except TimeoutError:
            continue
