from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

from src.agents.communication_agent import CommunicationAgentService
from src.models.communication import EscalationLevel, HITLNotification

from .config import EscalationConfig, get_escalation_config


class CosmosEscalationStore:
    def __init__(self, config: EscalationConfig) -> None:
        self._config = config
        self._client: Any | None = None

    async def list_pending_reviews(self) -> list[dict[str, Any]]:
        container = await self._get_container()
        query = (
            "SELECT TOP @limit * FROM c WHERE c.status IN ('pending', 'reminded', 'escalated') "
            "ORDER BY c.created_at ASC"
        )
        parameters = [{"name": "@limit", "value": self._config.query_batch_size}]
        return [dict(item) async for item in container.query_items(query=query, parameters=parameters)]

    async def upsert_item(self, document: dict[str, Any]) -> dict[str, Any]:
        container = await self._get_container()
        await container.upsert_item(document)
        return document

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()

    async def _get_container(self) -> Any:
        if self._client is None:
            try:
                from azure.cosmos.aio import CosmosClient
            except ModuleNotFoundError as exc:  # pragma: no cover - optional runtime dependency.
                raise RuntimeError("azure-cosmos is required for the escalation store.") from exc
            self._client = CosmosClient(self._config.cosmos_endpoint, credential=self._config.create_credential())
        database = self._client.get_database_client(self._config.database_name)
        return database.get_container_client(self._config.processing_container_name)


class EscalationScheduler:
    def __init__(
        self,
        review_store: Any,
        communication_service: CommunicationAgentService,
        config: EscalationConfig | None = None,
    ) -> None:
        self.review_store = review_store
        self.communication_service = communication_service
        self.config = config or get_escalation_config()

    async def run_once(self, now: datetime | None = None) -> list[HITLNotification]:
        current_time = now or datetime.now(tz=UTC)
        notifications: list[HITLNotification] = []
        for review_record in await self.review_store.list_pending_reviews():
            next_level = self.determine_next_level(review_record, now=current_time)
            if next_level is None:
                continue
            notification = await self.communication_service.handle_hitl_review(
                review_record,
                escalation_level=next_level,
            )
            notifications.append(notification)
        return notifications

    def determine_next_level(
        self,
        review_record: dict[str, Any],
        *,
        now: datetime,
    ) -> EscalationLevel | None:
        created_at = self._parse_datetime(review_record.get("created_at"))
        if created_at is None:
            return None
        elapsed = now - created_at
        current_level = EscalationLevel(str(review_record.get("escalation_level") or EscalationLevel.INITIAL.value))
        thresholds: Iterable[tuple[timedelta, EscalationLevel]] = (
            (timedelta(hours=self.config.final_after_hours), EscalationLevel.FINAL_72H),
            (timedelta(hours=self.config.escalation_after_hours), EscalationLevel.ESCALATION_48H),
            (timedelta(hours=self.config.reminder_after_hours), EscalationLevel.REMINDER_24H),
        )
        for threshold, escalation_level in thresholds:
            if elapsed < threshold:
                continue
            if escalation_level == EscalationLevel.REMINDER_24H and current_level == EscalationLevel.INITIAL:
                return escalation_level
            if escalation_level == EscalationLevel.ESCALATION_48H and current_level in {
                EscalationLevel.INITIAL,
                EscalationLevel.REMINDER_24H,
            }:
                return escalation_level
            if escalation_level == EscalationLevel.FINAL_72H and current_level != EscalationLevel.EXPIRED:
                return escalation_level
        return None

    def _parse_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        if isinstance(value, str) and value.strip():
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return None
