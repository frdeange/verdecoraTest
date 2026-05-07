from __future__ import annotations

import json
import os
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from agent_framework.openai import OpenAIChatCompletionClient
from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ResourceExistsError,
    ResourceNotFoundError,
)
from azure.cosmos import CosmosClient, PartitionKey
from azure.identity import DefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus.management import ServiceBusAdministrationClient
from azure.storage.blob import BlobServiceClient

from src.services.orchestrator.config import OrchestratorConfig
from src.services.orchestrator.handler import deserialize_message
from src.services.orchestrator.orchestration import OrchestratorService

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

SERVICE_BUS_NAMESPACE = "sb-albaranes-dev.servicebus.windows.net"
SERVICE_BUS_QUEUE = "albaran-incoming"
STORAGE_ACCOUNT_URL = "https://stalbaranesdev.blob.core.windows.net"
STORAGE_CONTAINER = "albaranes-raw"
AZURE_AI_ENDPOINT = "https://verdecora-ais-dev.cognitiveservices.azure.com/"
DOCINTELL_ENDPOINT = "https://verdecora-docintell-dev.cognitiveservices.azure.com/"
COSMOS_ENDPOINT = "https://cosmos-albaranes-dev.documents.azure.com:443/"
COSMOS_DATABASE = "albaranes-db"
PROCESSING_CONTAINER = "processing-records"
OPENAI_API_VERSION = "2024-12-01-preview"


def _require_live_azure() -> None:
    if os.getenv("RUN_LIVE_AZURE_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_AZURE_TESTS=1 to run live Azure orchestrator integration tests.")


def _skip_if_service_bus_blocked(exc: ClientAuthenticationError) -> None:
    detail = str(exc)
    if "Ip has been prevented to connect" in detail:
        pytest.skip(f"Service Bus data plane is blocked from this runner: {detail}")


def _skip_if_live_access_unavailable(exc: Exception) -> None:
    detail = str(exc)
    if (
        "Ip has been prevented to connect" in detail
        or "AuthorizationFailure" in detail
        or "This request is not authorized to perform this operation" in detail
    ):
        pytest.skip(f"Live Azure dependency is blocked from this runner: {detail}")


def _ensure_queue_exists(credential: DefaultAzureCredential) -> None:
    admin_client = ServiceBusAdministrationClient(
        fully_qualified_namespace=SERVICE_BUS_NAMESPACE,
        credential=credential,
    )
    try:
        try:
            admin_client.get_queue(SERVICE_BUS_QUEUE)
        except ResourceNotFoundError:
            admin_client.create_queue(SERVICE_BUS_QUEUE)
    finally:
        admin_client.close()


def _ensure_processing_container(credential: DefaultAzureCredential) -> None:
    cosmos_client = CosmosClient(COSMOS_ENDPOINT, credential=credential)
    try:
        database = cosmos_client.create_database_if_not_exists(COSMOS_DATABASE)
        database.create_container_if_not_exists(
            id=PROCESSING_CONTAINER,
            partition_key=PartitionKey(path="/id"),
        )
    finally:
        cosmos_client.close()


def _upload_test_blob(credential: DefaultAzureCredential, pdf_bytes: bytes, blob_name: str) -> tuple[str, str | None]:
    blob_service = BlobServiceClient(account_url=STORAGE_ACCOUNT_URL, credential=credential)
    try:
        container = blob_service.get_container_client(STORAGE_CONTAINER)
        try:
            container.create_container()
        except ResourceExistsError:
            pass
        blob_client = container.get_blob_client(blob_name)
        blob_client.upload_blob(pdf_bytes, overwrite=True, content_type="application/pdf")
        properties = blob_client.get_blob_properties()
        return blob_client.url, properties.etag
    finally:
        blob_service.close()


def _delete_test_blob(credential: DefaultAzureCredential, blob_name: str) -> None:
    blob_service = BlobServiceClient(account_url=STORAGE_ACCOUNT_URL, credential=credential)
    try:
        container = blob_service.get_container_client(STORAGE_CONTAINER)
        with suppress(ResourceNotFoundError):
            container.delete_blob(blob_name)
    finally:
        blob_service.close()


async def _receive_test_message(
    service_bus_client: ServiceBusClient,
    *,
    message_id: str,
    timeout_seconds: float = 45.0,
) -> object:
    deadline = time.monotonic() + timeout_seconds
    async with service_bus_client.get_queue_receiver(queue_name=SERVICE_BUS_QUEUE) as receiver:
        while time.monotonic() < deadline:
            messages = await receiver.receive_messages(max_message_count=5, max_wait_time=5)
            for message in messages:
                if str(getattr(message, "message_id", "")) == message_id:
                    await receiver.complete_message(message)
                    return message
                await receiver.abandon_message(message)
    raise AssertionError(f"Timed out waiting for message {message_id} on {SERVICE_BUS_QUEUE}")


@pytest.mark.asyncio
async def test_orchestrator_processes_live_service_bus_blob_event_end_to_end() -> None:
    _require_live_azure()
    os.environ.setdefault("DOCINTELL_ENDPOINT", DOCINTELL_ENDPOINT)

    repo_root = Path(__file__).resolve().parents[2]
    pdf_bytes = (repo_root / "prerequisites" / "PRUEBA.pdf").read_bytes()
    event_id = f"orch-e2e-{uuid4()}"
    message_id = f"sb-{event_id}"
    blob_name = f"2026/05/tienda_007/{event_id}.pdf"
    blob_url: str | None = None

    sync_credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    async_credential = AsyncDefaultAzureCredential(exclude_interactive_browser_credential=True)
    service_bus_client: ServiceBusClient | None = None
    orchestrator: OrchestratorService | None = None

    try:
        try:
            _ensure_queue_exists(sync_credential)
        except ClientAuthenticationError as exc:
            _skip_if_service_bus_blocked(exc)
            raise
        try:
            _ensure_processing_container(sync_credential)
            blob_url, blob_etag = _upload_test_blob(sync_credential, pdf_bytes, blob_name)
        except (ClientAuthenticationError, HttpResponseError) as exc:
            _skip_if_live_access_unavailable(exc)
            raise

        event_payload = [
            {
                "id": event_id,
                "eventType": "Microsoft.Storage.BlobCreated",
                "subject": f"/blobServices/default/containers/{STORAGE_CONTAINER}/blobs/{blob_name}",
                "eventTime": datetime.now(tz=UTC).isoformat(),
                "data": {
                    "api": "PutBlob",
                    "eTag": blob_etag,
                    "contentType": "application/pdf",
                    "contentLength": len(pdf_bytes),
                    "url": blob_url,
                    "metadata": {
                        "source": "pytest-live",
                        "supplier_hint": "HERSTERA",
                        "total_amount": "1.0",
                    },
                },
            }
        ]

        service_bus_client = ServiceBusClient(
            fully_qualified_namespace=SERVICE_BUS_NAMESPACE,
            credential=async_credential,
        )
        try:
            async with service_bus_client.get_queue_sender(queue_name=SERVICE_BUS_QUEUE) as sender:
                await sender.send_messages(
                    ServiceBusMessage(
                        json.dumps(event_payload),
                        content_type="application/json",
                        message_id=message_id,
                        subject="Microsoft.Storage.BlobCreated",
                    )
                )

            received_message = await _receive_test_message(service_bus_client, message_id=message_id)
        except ClientAuthenticationError as exc:
            _skip_if_service_bus_blocked(exc)
            raise
        request = deserialize_message(received_message)

        config = OrchestratorConfig(
            service_bus_namespace=SERVICE_BUS_NAMESPACE,
            extraction_queue_name=SERVICE_BUS_QUEUE,
            storage_account_url=STORAGE_ACCOUNT_URL,
            cosmos_endpoint=COSMOS_ENDPOINT,
            database_name=COSMOS_DATABASE,
            processing_container_name=PROCESSING_CONTAINER,
            azure_ai_project_endpoint=AZURE_AI_ENDPOINT,
            docintell_endpoint=DOCINTELL_ENDPOINT,
            service_bus_polling_enabled=False,
        )
        gpt5_client = OpenAIChatCompletionClient(
            model=config.gpt5_deployment,
            azure_endpoint=AZURE_AI_ENDPOINT,
            credential=async_credential,
            api_version=OPENAI_API_VERSION,
        )
        gpt5_mini_client = OpenAIChatCompletionClient(
            model=config.gpt5_mini_deployment,
            azure_endpoint=AZURE_AI_ENDPOINT,
            credential=async_credential,
            api_version=OPENAI_API_VERSION,
        )
        orchestrator = OrchestratorService(
            config=config,
            gpt5_client=gpt5_client,
            gpt5_mini_client=gpt5_mini_client,
        )

        try:
            result = await orchestrator.process_document(request)
        except (ClientAuthenticationError, HttpResponseError) as exc:
            _skip_if_live_access_unavailable(exc)
            raise

        assert result.processing_id == event_id
        assert result.blob_url == blob_url
        assert result.status == "completed"
        assert result.routing_decision == "extract"
        assert result.downloaded_bytes == len(pdf_bytes)
        assert result.pipeline_result["triage"] is not None
        assert result.pipeline_result["extraction"] is not None
        assert result.pipeline_result["coherence"] is None
        assert result.pipeline_result["validation"] is None
        assert result.pipeline_result["inventory"] is None
    finally:
        if orchestrator is not None:
            await orchestrator.close()
        if service_bus_client is not None:
            await service_bus_client.close()
        if blob_url is not None:
            _delete_test_blob(sync_credential, blob_name)
        await async_credential.close()
        sync_credential.close()
