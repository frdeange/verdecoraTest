from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator, Callable
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio

from src.agents.pipeline import AlbaranPipeline
from src.services.flow0_dedup.dedup_handler import Flow0DedupHandler
from src.services.orchestrator.config import OrchestratorConfig
from src.services.orchestrator.orchestration import OrchestratorService
from src.upload_web.app import create_app
from tests.unit.agent_test_helpers import FakeAsyncStream, FakeEvent, FakeWorkflow

pytestmark = pytest.mark.e2e


class SharedCosmosStore:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}


class SyncCosmosContainer:
    def __init__(self, store: SharedCosmosStore) -> None:
        self._store = store

    def query_items(self, *, parameters: list[dict[str, Any]], **_: Any) -> list[dict[str, Any]]:
        parameter_map = {parameter["name"]: parameter["value"] for parameter in parameters}
        dedup_key = parameter_map.get("@dedup_key")
        blob_name = parameter_map.get("@blob_name")
        event_date = parameter_map.get("@event_date")
        matches = [
            item
            for item in self._store.items.values()
            if item.get("dedup_key") == dedup_key
            or (item.get("blob_name") == blob_name and item.get("event_date") == event_date)
        ]
        return matches[:1]

    def upsert_item(self, *, body: dict[str, Any]) -> dict[str, Any]:
        self._store.items[str(body["id"])] = dict(body)
        return dict(body)


class AsyncCosmosContainer:
    def __init__(self, store: SharedCosmosStore) -> None:
        self._store = store

    async def upsert_item(self, body: dict[str, Any]) -> dict[str, Any]:
        self._store.items[str(body["id"])] = dict(body)
        return dict(body)


class FakeFlow0Sender:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def send_messages(self, message: Any) -> None:
        body = b"".join(bytes(part) for part in message.body)
        self.messages.append(json.loads(body.decode("utf-8")))


class FakeQueueSender:
    def __init__(self, queue_name: str, sent_messages: list[dict[str, Any]]) -> None:
        self._queue_name = queue_name
        self._sent_messages = sent_messages

    async def __aenter__(self) -> "FakeQueueSender":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def send_messages(self, message: Any) -> None:
        body = b"".join(bytes(part) for part in message.body)
        self._sent_messages.append({"queue_name": self._queue_name, "payload": json.loads(body.decode("utf-8"))})


class FakeAsyncServiceBusClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []

    def get_queue_sender(self, *, queue_name: str) -> FakeQueueSender:
        return FakeQueueSender(queue_name, self.sent_messages)


class FakeDependencies:
    def __init__(self, store: SharedCosmosStore, service_bus_client: FakeAsyncServiceBusClient) -> None:
        self._container = AsyncCosmosContainer(store)
        self._service_bus_client = service_bus_client

    async def get_processing_container(self) -> AsyncCosmosContainer:
        return self._container

    def get_service_bus_client(self) -> FakeAsyncServiceBusClient:
        return self._service_bus_client

    async def close(self) -> None:
        return None


class FakeReceivedMessage:
    def __init__(self, payload: dict[str, Any], *, delivery_count: int = 1) -> None:
        self.body = [json.dumps(payload).encode("utf-8")]
        self.delivery_count = delivery_count


class FakeReceiver:
    def __init__(self) -> None:
        self.completed_messages: list[FakeReceivedMessage] = []
        self.abandoned_messages: list[FakeReceivedMessage] = []
        self.dead_lettered_messages: list[dict[str, Any]] = []

    async def complete_message(self, message: FakeReceivedMessage) -> None:
        self.completed_messages.append(message)

    async def abandon_message(self, message: FakeReceivedMessage) -> None:
        self.abandoned_messages.append(message)

    async def dead_letter_message(self, message: FakeReceivedMessage, *, reason: str, error_description: str) -> None:
        self.dead_lettered_messages.append(
            {"message": message, "reason": reason, "error_description": error_description}
        )


class FakeWorkflowResult:
    def __init__(self, payload: Any) -> None:
        self.payload = payload


def _to_workflow_response(response: Any) -> Any:
    if isinstance(response, list):
        return FakeAsyncStream([FakeEvent(item) for item in response])
    return response


@pytest.fixture(scope="session")
def full_pipeline_test_skeleton(
    sample_albaran_data: dict[str, object], sample_po_data: dict[str, object]
) -> dict[str, Any]:
    return {
        "name": "albaran-to-business-central",
        "stages": [
            "blob-created-event",
            "flow-0-dedup",
            "agent-a1-triage",
            "agent-a2-extraction",
            "agent-a3-coherence",
            "agent-a4-validator",
            "agent-a5-inventory",
            "acs-hitl-notification",
        ],
        "inputs": {
            "blob_path": sample_albaran_data["blob_path"],
            "albaran_id": sample_albaran_data["id"],
            "purchase_order": sample_po_data["number"],
        },
        "expected_terminal_states": [
            "inventariado",
            "rechazado",
            "escalado",
            "completed",
            "rejected",
            "hitl_pending",
        ],
    }


@pytest.fixture()
def sample_blob_event() -> dict[str, Any]:
    return {
        "id": "evt-e2e-001",
        "eventType": "Microsoft.Storage.BlobCreated",
        "subject": "/blobServices/default/containers/albaranes-raw/blobs/2026/05/tienda_007/albaran-herstera.pdf",
        "eventTime": "2026-05-04T08:12:33Z",
        "data": {
            "eTag": '"0x8DEADBEEF"',
            "contentType": "application/pdf",
            "contentLength": 2048,
            "url": "https://storage.blob.core.windows.net/albaranes-raw/2026/05/tienda_007/albaran-herstera.pdf",
            "metadata": {"blob_hash": "hash-e2e-001", "source": "pytest"},
        },
    }


@pytest.fixture()
def ocr_payload() -> dict[str, Any]:
    return {
        "content": "ALBARAN DE ENTREGA HERSTERA PO-2026-0456",
        "page_count": 1,
        "tables": [{"row_count": 2, "column_count": 5}],
        "key_value_pairs": [{"key": "purchase_order", "value": "PO-2026-0456", "confidence": 0.99}],
    }


@pytest.fixture()
def cosmos_store() -> SharedCosmosStore:
    return SharedCosmosStore()


@pytest.fixture()
def flow0_handler(cosmos_store: SharedCosmosStore) -> tuple[Flow0DedupHandler, FakeFlow0Sender]:
    sender = FakeFlow0Sender()
    handler = Flow0DedupHandler(SyncCosmosContainer(cosmos_store), sender)
    return handler, sender


@pytest.fixture()
def fake_receiver() -> FakeReceiver:
    return FakeReceiver()


@pytest.fixture()
def workflow_factory() -> Callable[[dict[str, Any]], tuple[dict[str, FakeWorkflow], Callable[..., Any]]]:
    def _build(responses: dict[str, Any]) -> tuple[dict[str, FakeWorkflow], Callable[..., Any]]:
        workflows = {name: FakeWorkflow(_to_workflow_response(response)) for name, response in responses.items()}

        def fake_builder(*, participants: list[Any]) -> Any:
            key = ">".join(getattr(participant, "name", str(participant)).casefold() for participant in participants)
            return SimpleNamespace(build=lambda: workflows[key])

        return workflows, fake_builder

    return _build


@pytest.fixture()
def orchestrator_factory(
    cosmos_store: SharedCosmosStore, ocr_payload: dict[str, Any]
) -> Callable[[], tuple[OrchestratorService, FakeAsyncServiceBusClient]]:
    def _build() -> tuple[OrchestratorService, FakeAsyncServiceBusClient]:
        config = OrchestratorConfig(service_bus_polling_enabled=False)
        service = OrchestratorService(config=config, agent_client=object())
        service_bus_client = FakeAsyncServiceBusClient()
        service.dependencies = FakeDependencies(cosmos_store, service_bus_client)
        service.pipeline = AlbaranPipeline(
            agents={
                "triage": SimpleNamespace(name="triage"),
                "extractor": SimpleNamespace(name="extractor"),
                "coherence": SimpleNamespace(name="coherence"),
                "validator": SimpleNamespace(name="validator"),
                "inventory": SimpleNamespace(name="inventory"),
                "communication": SimpleNamespace(name="communication"),
            }
        )
        service.download_blob = AsyncMock(return_value=b"%PDF-1.7 mocked pdf bytes")
        service.analyze_document = AsyncMock(return_value=ocr_payload)
        return service, service_bus_client

    return _build


@pytest_asyncio.fixture()
async def app_client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    principal = {
        "auth_typ": "aad",
        "claims": [
            {
                "typ": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier",
                "val": "oid-e2e-smoke-001",
            },
            {"typ": "name", "val": "Vasquez QA"},
            {"typ": "preferred_username", "val": "vasquez.qa@verdecora.example"},
            {"typ": "groups", "val": "verdecora-store-uploaders"},
            {"typ": "exp", "val": "9999999999"},
        ],
        "name_typ": "name",
        "role_typ": "roles",
    }
    encoded_principal = base64.b64encode(json.dumps(principal).encode("utf-8")).decode("utf-8")
    return {
        "X-MS-CLIENT-PRINCIPAL": encoded_principal,
        "X-MS-CLIENT-PRINCIPAL-ID": "oid-e2e-smoke-001",
        "X-MS-CLIENT-PRINCIPAL-NAME": "Vasquez QA",
        "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
    }
