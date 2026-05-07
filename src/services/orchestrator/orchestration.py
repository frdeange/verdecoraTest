from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from src.agents.pipeline import AlbaranPipeline, PipelineDocumentInput
from src.config.agents import get_agents_config

from .config import OrchestratorConfig, get_orchestrator_config


class OrchestrationRequest(BaseModel):
    blob_url: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    processing_id: str | None = None


class OrchestrationResult(BaseModel):
    processing_id: str
    blob_url: str
    status: str
    routing_decision: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    pipeline_result: dict[str, Any] = Field(default_factory=dict)
    downloaded_bytes: int = 0
    error: str | None = None


class OrchestrationError(RuntimeError):
    def __init__(self, message: str, *, result: OrchestrationResult) -> None:
        super().__init__(message)
        self.result = result


class AzureDependencySet:
    def __init__(self, config: OrchestratorConfig) -> None:
        self.config = config
        self._credential: Any | None = None
        self._cosmos_client: Any | None = None
        self._service_bus_client: Any | None = None

    def get_credential(self) -> Any:
        if self._credential is None:
            self._credential = self.config.create_credential()
        return self._credential

    def get_service_bus_client(self) -> Any:
        if self._service_bus_client is None:
            try:
                from azure.servicebus.aio import ServiceBusClient
            except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional runtime dependency.
                raise RuntimeError("azure-servicebus is required for Service Bus queue processing.") from exc
            self._service_bus_client = ServiceBusClient(
                fully_qualified_namespace=self.config.service_bus_fully_qualified_namespace,
                credential=self.get_credential(),
            )
        return self._service_bus_client

    def get_cosmos_client(self) -> Any:
        if self._cosmos_client is None:
            try:
                from azure.cosmos.aio import CosmosClient
            except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional runtime dependency.
                raise RuntimeError("azure-cosmos is required for orchestrator processing records.") from exc
            self._cosmos_client = CosmosClient(self.config.cosmos_endpoint, credential=self.get_credential())
        return self._cosmos_client

    async def get_processing_container(self) -> Any:
        cosmos_client = self.get_cosmos_client()
        database_client = cosmos_client.get_database_client(self.config.database_name)
        return database_client.get_container_client(self.config.processing_container_name)

    async def check_ready(self) -> dict[str, Any]:
        checks: dict[str, str] = {}
        errors: dict[str, str] = {}

        for name, factory in {
            "credential": self.get_credential,
            "cosmos": self.get_cosmos_client,
            "service_bus": self.get_service_bus_client,
        }.items():
            try:
                factory()
            except Exception as exc:  # pragma: no cover - best-effort readiness verification.
                errors[name] = str(exc)
            else:
                checks[name] = "configured"

        try:
            from azure.storage.blob.aio import BlobClient
        except ModuleNotFoundError as exc:  # pragma: no cover - optional runtime dependency.
            errors["storage"] = str(exc)
        else:
            checks["storage"] = f"ready:{BlobClient.__name__}"

        try:
            from src.mcp.content_understanding_mcp.server import get_document_intelligence_client
        except Exception as exc:  # pragma: no cover - optional runtime dependency.
            errors["document_intelligence"] = str(exc)
        else:
            try:
                await asyncio.to_thread(get_document_intelligence_client)
            except Exception as exc:  # pragma: no cover - best-effort readiness verification.
                errors["document_intelligence"] = str(exc)
            else:
                checks["document_intelligence"] = "configured"

        return {"ready": not errors, "checks": checks, "errors": errors}

    async def close(self) -> None:
        for attribute_name in ("_service_bus_client", "_cosmos_client", "_credential"):
            resource = getattr(self, attribute_name)
            if resource is not None and hasattr(resource, "close"):
                maybe_close = resource.close()
                if asyncio.iscoroutine(maybe_close):
                    await maybe_close


class OrchestratorService:
    def __init__(
        self,
        config: OrchestratorConfig | None = None,
        *,
        agent_client: Any | None = None,
        gpt5_client: Any | None = None,
        gpt5_mini_client: Any | None = None,
    ) -> None:
        self.config = config or get_orchestrator_config()
        self.dependencies = AzureDependencySet(self.config)
        if agent_client is not None:
            gpt5_client = gpt5_client or agent_client
            gpt5_mini_client = gpt5_mini_client or agent_client
        self.pipeline = AlbaranPipeline(
            config=get_agents_config(),
            project_endpoint=self.config.azure_ai_project_endpoint,
            credential=self.dependencies.get_credential(),
            gpt5_client=gpt5_client,
            gpt5_mini_client=gpt5_mini_client,
        )
        self.gpt5_client = self.pipeline.gpt5_client
        self.gpt5_mini_client = self.pipeline.gpt5_mini_client
        self.agent_client = self.gpt5_client

    async def close(self) -> None:
        closed_clients: set[int] = set()
        for client in (self.gpt5_client, self.gpt5_mini_client):
            if client is None or id(client) in closed_clients or not hasattr(client, "close"):
                continue
            maybe_close = client.close()
            if asyncio.iscoroutine(maybe_close):
                await maybe_close
            closed_clients.add(id(client))
        await self.dependencies.close()

    async def check_readiness(self) -> dict[str, Any]:
        readiness = await self.dependencies.check_ready()
        readiness["queue_name"] = self.config.extraction_queue_name
        readiness["hitl_queue_name"] = self.config.hitl_queue_name
        return readiness

    def _build_processing_id(self, request: OrchestrationRequest) -> str:
        if request.processing_id:
            return request.processing_id
        digest = hashlib.sha1(
            json.dumps({"blob_url": request.blob_url, "metadata": request.metadata}, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return digest

    async def download_blob(self, blob_url: str) -> bytes:
        try:
            from azure.storage.blob.aio import BlobClient
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional runtime dependency.
            raise RuntimeError("azure-storage-blob is required for blob downloads.") from exc

        blob_client = BlobClient.from_blob_url(blob_url, credential=self.dependencies.get_credential())
        try:
            downloader = await blob_client.download_blob()
            return await downloader.readall()
        finally:
            await blob_client.close()

    async def analyze_document(self, blob_url: str, *, document_bytes: bytes | None = None) -> dict[str, Any]:
        os.environ.setdefault("DOCINTELL_ENDPOINT", self.config.docintell_endpoint)
        from src.mcp.content_understanding_mcp.server import run_analysis, to_key_value_pairs, to_tables

        analysis_source = (
            base64.b64encode(document_bytes).decode("ascii") if document_bytes is not None else blob_url
        )
        analysis_result = await asyncio.to_thread(run_analysis, analysis_source, "prebuilt-layout")
        return {
            "content": analysis_result.content,
            "page_count": len(analysis_result.pages or []),
            "tables": [table.model_dump(mode="json") for table in to_tables(analysis_result)],
            "key_value_pairs": [pair.model_dump(mode="json") for pair in to_key_value_pairs(analysis_result)],
        }

    async def _write_processing_record(self, result: OrchestrationResult) -> None:
        container = await self.dependencies.get_processing_container()
        record = result.model_dump(mode="json")
        record["id"] = result.processing_id
        if result.metadata.get("upload_session_id"):
            record["upload_session_id"] = result.metadata["upload_session_id"]
        if result.metadata.get("uploader_oid"):
            record["uploader_oid"] = result.metadata["uploader_oid"]
        await container.upsert_item(record)

    async def _write_processing_status(
        self,
        *,
        processing_id: str,
        blob_url: str,
        status: str,
        metadata: dict[str, Any],
        routing_decision: str = "processing",
        error: str | None = None,
    ) -> None:
        await self._write_processing_record(
            OrchestrationResult(
                processing_id=processing_id,
                blob_url=blob_url,
                status=status,
                routing_decision=routing_decision,
                metadata=metadata,
                error=error,
            )
        )

    async def _send_hitl_message(self, result: OrchestrationResult) -> None:
        try:
            from azure.servicebus import ServiceBusMessage
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional runtime dependency.
            raise RuntimeError("azure-servicebus is required for HITL handoff messages.") from exc

        sender_payload = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
        service_bus_client = self.dependencies.get_service_bus_client()
        async with service_bus_client.get_queue_sender(queue_name=self.config.hitl_queue_name) as sender:
            await sender.send_messages(ServiceBusMessage(sender_payload, content_type="application/json"))

    def _extract_total_amount(self, metadata: dict[str, Any]) -> float | None:
        raw_total = metadata.get("total_amount")
        if raw_total is None:
            return None
        try:
            return float(raw_total)
        except (TypeError, ValueError):
            return None

    def _build_pipeline_input(
        self,
        *,
        blob_url: str,
        metadata: dict[str, Any],
        ocr_payload: dict[str, Any],
    ) -> PipelineDocumentInput:
        return PipelineDocumentInput(
            document_reference=blob_url,
            raw_text=str(ocr_payload.get("content") or "") or None,
            ocr_payload=ocr_payload,
            supplier_id=self._get_optional_str(metadata, "supplier_id"),
            supplier_hint=self._get_optional_str(metadata, "supplier_hint"),
            total_amount=self._extract_total_amount(metadata),
            metadata=metadata,
        )

    def _resolve_status(self, routing_decision: str) -> str:
        if routing_decision in {"posted", "approve", "extract"}:
            return "completed"
        if routing_decision == "hitl_review":
            return "hitl_pending"
        if routing_decision == "reject":
            return "rejected"
        return "failed"

    def _get_optional_str(self, payload: dict[str, Any], key: str) -> str | None:
        value = payload.get(key)
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    async def process_document(self, request: OrchestrationRequest | dict[str, Any]) -> OrchestrationResult:
        normalized_request = request
        if not isinstance(request, OrchestrationRequest):
            normalized_request = OrchestrationRequest.model_validate(request)

        processing_id = self._build_processing_id(normalized_request)
        await self._write_processing_status(
            processing_id=processing_id,
            blob_url=normalized_request.blob_url,
            status="processing",
            metadata=normalized_request.metadata,
        )

        try:
            blob_bytes = await self.download_blob(normalized_request.blob_url)
            ocr_payload = await self.analyze_document(normalized_request.blob_url, document_bytes=blob_bytes)
            pipeline_result = await self.pipeline.run(
                self._build_pipeline_input(
                    blob_url=normalized_request.blob_url,
                    metadata=normalized_request.metadata,
                    ocr_payload=ocr_payload,
                )
            )
            result = OrchestrationResult(
                processing_id=processing_id,
                blob_url=normalized_request.blob_url,
                status=self._resolve_status(pipeline_result.routing_decision),
                routing_decision=pipeline_result.routing_decision,
                metadata=normalized_request.metadata,
                pipeline_result=pipeline_result.model_dump(mode="json"),
                downloaded_bytes=len(blob_bytes),
            )
            await self._write_processing_record(result)
            if result.status == "hitl_pending":
                await self._send_hitl_message(result)
            return result
        except Exception as exc:
            failure_result = OrchestrationResult(
                processing_id=processing_id,
                blob_url=normalized_request.blob_url,
                status="failed",
                routing_decision="failed",
                metadata=normalized_request.metadata,
                error=str(exc),
            )
            await self._write_processing_record(failure_result)
            raise OrchestrationError(
                f"Processing failed for {normalized_request.blob_url}", result=failure_result
            ) from exc


def blob_path_from_url(blob_url: str) -> tuple[str, str]:
    parsed_url = urlparse(blob_url)
    path_segments = [segment for segment in parsed_url.path.split("/") if segment]
    if len(path_segments) < 2:
        raise ValueError(f"Blob URL must include container and blob path: {blob_url}")
    return path_segments[0], "/".join(path_segments[1:])
