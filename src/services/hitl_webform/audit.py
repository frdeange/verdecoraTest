from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from src.config.security import get_managed_identity_credential

LOGGER = logging.getLogger("hitl.audit")


class CosmosContainer(Protocol):
    async def upsert_item(self, body: dict[str, Any]) -> Any:  # pragma: no cover - protocol definition
        ...


class HITLDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    albaran_id: str
    action: str
    reviewer_email: str
    comment: str | None = None
    modified_quantity: float | None = None
    store_id: str | None = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditLogger:
    """Write immutable HITL audit records to Cosmos DB using managed identity."""

    def __init__(
        self,
        cosmos_endpoint: str | None = None,
        *,
        database_name: str = "albaranes-db",
        container_name: str = "hitl-audit",
        container_client: CosmosContainer | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._cosmos_endpoint = cosmos_endpoint
        self._database_name = database_name
        self._container_name = container_name
        self._container_client = container_client
        self._logger = logger or LOGGER
        self._cosmos_client: Any | None = None

    async def log_decision(self, decision: HITLDecision, reviewer_ip: str, correlation_id: str) -> None:
        event_time = decision.decided_at.astimezone(UTC)
        document = {
            "id": f"{decision.albaran_id}:decision:{uuid4()}",
            "pk": decision.albaran_id,
            "eventType": "hitl.decision",
            "albaranId": decision.albaran_id,
            "action": decision.action,
            "reviewerEmail": decision.reviewer_email.casefold(),
            "reviewerIp": reviewer_ip,
            "comment": decision.comment,
            "modifiedQuantity": decision.modified_quantity,
            "storeId": decision.store_id,
            "correlationId": correlation_id,
            "createdAt": event_time.isoformat(),
        }
        await self._write_event(document)
        self._logger.info(
            "Recorded HITL decision audit event",
            extra={
                "correlation_id": correlation_id,
                "albaran_id": decision.albaran_id,
                "reviewer_email": decision.reviewer_email.casefold(),
                "action": decision.action,
            },
        )

    async def log_pdf_access(self, albaran_id: str, user_email: str, correlation_id: str) -> None:
        event_time = datetime.now(UTC)
        document = {
            "id": f"{albaran_id}:pdf-access:{uuid4()}",
            "pk": albaran_id,
            "eventType": "hitl.pdf_access",
            "albaranId": albaran_id,
            "userEmail": user_email.casefold(),
            "correlationId": correlation_id,
            "createdAt": event_time.isoformat(),
        }
        await self._write_event(document)
        self._logger.info(
            "Recorded HITL PDF access audit event",
            extra={
                "correlation_id": correlation_id,
                "albaran_id": albaran_id,
                "user_email": user_email.casefold(),
            },
        )

    async def _write_event(self, document: dict[str, Any]) -> None:
        container_client = await self._get_container_client()
        await container_client.upsert_item(body=document)

    async def _get_container_client(self) -> CosmosContainer:
        if self._container_client is not None:
            return self._container_client

        if not self._cosmos_endpoint:
            raise RuntimeError("cosmos_endpoint is required when no container_client is supplied.")

        from azure.cosmos.aio import CosmosClient

        if self._cosmos_client is None:
            self._cosmos_client = CosmosClient(
                url=self._cosmos_endpoint,
                credential=get_managed_identity_credential(),
            )

        database_client = self._cosmos_client.get_database_client(self._database_name)
        self._container_client = database_client.get_container_client(self._container_name)
        return self._container_client

    async def close(self) -> None:
        if self._cosmos_client is not None:
            await self._cosmos_client.close()
            self._cosmos_client = None
