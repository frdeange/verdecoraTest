from __future__ import annotations

import logging
import os
from typing import Any

from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient

from src.services.flow0_dedup.dedup_handler import Flow0DedupHandler

LOGGER = logging.getLogger("flow0_dedup")


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _normalize_service_bus_namespace(value: str) -> str:
    return value if ".servicebus.windows.net" in value else f"{value}.servicebus.windows.net"


def _read_message_body(message: Any) -> str:
    body = message.body
    if isinstance(body, str):
        return body
    if isinstance(body, (bytes, bytearray)):
        return body.decode("utf-8")

    chunks: list[bytes] = []
    for chunk in body:
        if isinstance(chunk, bytes):
            chunks.append(chunk)
        else:
            chunks.append(bytes(chunk))
    return b"".join(chunks).decode("utf-8")


def run(max_message_count: int = 1) -> int:
    """Run one Flow 0 batch for the ACA Job execution."""

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    cosmos_client = CosmosClient(url=_require_env("COSMOS_ENDPOINT"), credential=credential)
    container_client = cosmos_client.get_database_client(
        os.getenv("COSMOS_DATABASE_NAME", "albaranes-db")
    ).get_container_client(os.getenv("COSMOS_CONTAINER_NAME", "albaranes"))

    service_bus_client = ServiceBusClient(
        fully_qualified_namespace=_normalize_service_bus_namespace(
            os.getenv("SERVICEBUS_FQ_NAMESPACE") or _require_env("SERVICE_BUS_NAMESPACE")
        ),
        credential=credential,
    )

    source_queue = os.getenv("FLOW0_SOURCE_QUEUE_NAME", "extraccion-queue")
    target_queue = os.getenv("FLOW0_TARGET_QUEUE_NAME", "extraccion-in")
    failures = 0

    with service_bus_client:
        with service_bus_client.get_queue_receiver(queue_name=source_queue, max_wait_time=10) as receiver:
            with service_bus_client.get_queue_sender(queue_name=target_queue) as sender:
                handler = Flow0DedupHandler(container_client=container_client, sender=sender, logger=LOGGER)
                messages = receiver.receive_messages(max_message_count=max_message_count, max_wait_time=10)
                if not messages:
                    LOGGER.info("No Flow 0 messages available", extra={"queue": source_queue})
                    return 0

                for message in messages:
                    try:
                        forwarded = handler.handle_message(_read_message_body(message))
                        receiver.complete_message(message)
                        LOGGER.info(
                            "Flow 0 message processed",
                            extra={"queue": source_queue, "forwarded": forwarded},
                        )
                    except Exception:  # noqa: BLE001 - log and abandon so ACA/KEDA can retry.
                        failures += 1
                        LOGGER.exception("Flow 0 message processing failed")
                        receiver.abandon_message(message)

    return failures


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
