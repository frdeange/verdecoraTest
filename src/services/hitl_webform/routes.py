from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.models.communication import HITLDecision

from .auth import validate_entra_token
from .templates import render_review_page

router = APIRouter()


class HITLDecisionRequest(BaseModel):
    decision: str
    modified_lines: list[dict[str, Any]] | None = None
    notes: str | None = None


class CosmosReviewStore:
    def __init__(self, config: Any) -> None:
        self._config = config
        self._client: Any | None = None

    async def get_review_record(self, albaran_id: str) -> dict[str, Any] | None:
        container = await self._get_container()
        query = "SELECT TOP 1 * FROM c WHERE c.id = @id"
        parameters = [{"name": "@id", "value": albaran_id}]
        items = [item async for item in container.query_items(query=query, parameters=parameters)]
        return dict(items[0]) if items else None

    async def upsert_item(self, document: dict[str, Any]) -> dict[str, Any]:
        container = await self._get_container()
        await container.upsert_item(document)
        return document

    async def save_decision(self, decision: HITLDecision) -> dict[str, Any]:
        record = (await self.get_review_record(decision.albaran_id)) or {"id": decision.albaran_id}
        record.update(
            {
                "status": "decided",
                "hitl_decision": decision.model_dump(mode="json"),
                "reviewer_email": decision.reviewer_email,
                "decided_at": decision.decided_at.isoformat(),
            }
        )
        await self.upsert_item(record)
        return record

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()

    async def _get_container(self) -> Any:
        if self._client is None:
            try:
                from azure.cosmos.aio import CosmosClient
            except ModuleNotFoundError as exc:  # pragma: no cover - optional runtime dependency.
                raise RuntimeError("azure-cosmos is required for the HITL webform store.") from exc
            self._client = CosmosClient(self._config.cosmos_endpoint, credential=self._config.create_credential())
        database = self._client.get_database_client(self._config.database_name)
        return database.get_container_client(self._config.processing_container_name)


class ServiceBusDecisionPublisher:
    def __init__(self, config: Any) -> None:
        self._config = config
        self._client: Any | None = None

    async def publish(self, decision: HITLDecision) -> None:
        try:
            from azure.servicebus import ServiceBusMessage
            from azure.servicebus.aio import ServiceBusClient
        except ModuleNotFoundError as exc:  # pragma: no cover - optional runtime dependency.
            raise RuntimeError("azure-servicebus is required for the HITL webform publisher.") from exc
        if self._client is None:
            self._client = ServiceBusClient(
                fully_qualified_namespace=self._config.service_bus_fully_qualified_namespace,
                credential=self._config.create_credential(),
            )
        payload = json.dumps(decision.model_dump(mode="json"), ensure_ascii=False)
        async with self._client.get_topic_sender(topic_name=self._config.hitl_decisions_topic_name) as sender:
            await sender.send_messages(ServiceBusMessage(payload, content_type="application/json"))

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/review/{albaran_id}", response_class=HTMLResponse)
async def get_review_page(
    albaran_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> HTMLResponse:
    config = cast(Any, request.app.state.hitl_config)
    reviewer = await validate_entra_token(authorization, config=config)
    review_store = cast(Any, request.app.state.review_store)
    review_record = await review_store.get_review_record(albaran_id)
    if review_record is None:
        raise HTTPException(status_code=404, detail="HITL review record not found.")
    return HTMLResponse(render_review_page(albaran_id, review_record, reviewer.email))


@router.post("/review/{albaran_id}/decide")
async def submit_review_decision(
    albaran_id: str,
    payload: HITLDecisionRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    config = cast(Any, request.app.state.hitl_config)
    reviewer = await validate_entra_token(authorization, config=config)
    if payload.decision not in {"approve", "reject", "modify"}:
        raise HTTPException(status_code=422, detail="decision must be approve, reject, or modify")
    review_store = cast(Any, request.app.state.review_store)
    publisher = cast(Any, request.app.state.decision_publisher)
    decision = HITLDecision(
        albaran_id=albaran_id,
        decision=payload.decision,
        modified_lines=payload.modified_lines,
        reviewer_email=reviewer.email,
        decided_at=datetime.now(tz=UTC),
        notes=payload.notes,
    )
    saved = review_store.save_decision(decision)
    if inspect.isawaitable(saved):
        await saved
    published = publisher.publish(decision)
    if inspect.isawaitable(published):
        await published
    return {"status": "accepted", "decision": decision.model_dump(mode="json")}
