from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from agent_framework import SequentialBuilder

from src.agents.factory import create_agents, create_clients
from src.mcp.feature_flags_mcp.server import set_flag, set_supplier_config
from src.models.learning import LearningInsight, LearningReport, SupplierReputation

from .config import LearningConfig, get_learning_config
from .flag_proposer import propose_feature_flag_updates
from .reputation import build_supplier_reputation


class CosmosLearningStore:
    def __init__(self, config: LearningConfig) -> None:
        self._config = config
        self._client: Any | None = None

    async def list_processed_records(self, *, since: datetime) -> list[dict[str, Any]]:
        container = await self._get_container()
        query = (
            "SELECT TOP @limit * FROM c WHERE "
            "(IS_DEFINED(c.created_at) AND c.created_at >= @since) OR "
            "(IS_DEFINED(c.updated_at) AND c.updated_at >= @since) OR "
            "(IS_DEFINED(c.completed_at) AND c.completed_at >= @since) "
            "ORDER BY c.created_at DESC"
        )
        parameters = [
            {"name": "@limit", "value": self._config.query_batch_size},
            {"name": "@since", "value": since.isoformat()},
        ]
        return [dict(item) async for item in container.query_items(query=query, parameters=parameters)]

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()

    async def _get_container(self) -> Any:
        if self._client is None:
            try:
                from azure.cosmos.aio import CosmosClient
            except ModuleNotFoundError as exc:  # pragma: no cover - optional runtime dependency.
                raise RuntimeError("azure-cosmos is required for the learning store.") from exc
            self._client = CosmosClient(self._config.cosmos_endpoint, credential=self._config.create_credential())
        database = self._client.get_database_client(self._config.database_name)
        return database.get_container_client(self._config.processing_container_name)


class LearningAnalyzer:
    def __init__(
        self,
        config: LearningConfig | None = None,
        *,
        history_store: Any | None = None,
        agent: Any | None = None,
        agent_runner: Callable[[dict[str, Any]], Any] | None = None,
        set_supplier_config_tool: Callable[..., dict[str, Any]] | None = None,
        set_flag_tool: Callable[..., dict[str, Any]] | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.config = config or get_learning_config()
        self.history_store = history_store or CosmosLearningStore(self.config)
        self.agent = agent
        self.agent_runner = agent_runner
        self.set_supplier_config_tool = set_supplier_config_tool or set_supplier_config
        self.set_flag_tool = set_flag_tool or set_flag
        self.now_provider = now_provider or (lambda: datetime.now(tz=UTC))
        self._owned_clients: list[Any] = []

    async def analyze(self) -> LearningReport:
        now = self.now_provider()
        since = now - timedelta(days=self.config.analysis_window_days)
        records = await self.history_store.list_processed_records(since=since)
        grouped = self._group_by_supplier(records)
        reputations = [
            build_supplier_reputation(supplier_id, supplier_name, supplier_records, now=now)
            for (supplier_id, supplier_name), supplier_records in grouped.items()
        ]
        fallback_insights = self._build_fallback_insights(reputations)
        draft_flag_proposals = propose_feature_flag_updates(reputations, fallback_insights)
        generated = await self._generate_report_with_agent(
            {
                "report_date": now.isoformat(),
                "suppliers_analyzed": len(grouped),
                "supplier_metrics": [reputation.model_dump(mode="json") for reputation in reputations],
                "feature_flag_proposals": draft_flag_proposals,
                "recent_records": records,
            }
        )

        report = LearningReport(
            report_date=now,
            suppliers_analyzed=len(grouped),
            insights=generated.insights if generated is not None and generated.insights else fallback_insights,
            reputation_updates=(
                generated.reputation_updates if generated is not None and generated.reputation_updates else reputations
            ),
            feature_flag_proposals=(
                generated.feature_flag_proposals
                if generated is not None and generated.feature_flag_proposals
                else draft_flag_proposals
            ),
            summary=generated.summary if generated is not None else self._build_summary(reputations),
        )
        self._persist_reputations(report.reputation_updates)
        if self.config.apply_feature_flag_proposals:
            self._apply_flag_proposals(report.feature_flag_proposals)
        return report

    async def close(self) -> None:
        if hasattr(self.history_store, "close"):
            maybe_close = self.history_store.close()
            if asyncio.iscoroutine(maybe_close):
                await maybe_close
        for client in self._owned_clients:
            if hasattr(client, "close"):
                maybe_close = client.close()
                if asyncio.iscoroutine(maybe_close):
                    await maybe_close

    def _group_by_supplier(self, records: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            supplier_id = _extract_supplier_id(record)
            supplier_name = _extract_supplier_name(record)
            if supplier_id is None or supplier_name is None:
                continue
            normalized_record = dict(record)
            normalized_record.setdefault("discrepancies", _extract_discrepancies(record))
            grouped[(supplier_id, supplier_name)].append(normalized_record)
        return grouped

    def _persist_reputations(self, reputations: list[SupplierReputation]) -> None:
        for reputation in reputations:
            self.set_supplier_config_tool(
                supplier_id=reputation.supplier_id,
                configuration=reputation.model_dump(mode="json"),
                description="Learning-generated supplier reputation profile.",
            )

    def _apply_flag_proposals(self, proposals: list[dict[str, str]]) -> None:
        for proposal in proposals:
            for flag_name, flag_value in proposal.items():
                self.set_flag_tool(
                    flag_name=flag_name,
                    value=flag_value,
                    description="Learning agent proposal applied automatically.",
                )

    def _build_fallback_insights(self, reputations: list[SupplierReputation]) -> list[LearningInsight]:
        insights: list[LearningInsight] = []
        for reputation in reputations:
            if reputation.auto_approve_eligible:
                insights.append(
                    LearningInsight(
                        insight_type="recommendation",
                        supplier_id=reputation.supplier_id,
                        description=(
                            f"{reputation.supplier_name} is consistently reliable and can be considered for auto-approve."
                        ),
                        confidence=min(reputation.reliability_score, 0.99),
                        suggested_flag_update={
                            f"supplier.{reputation.supplier_id}.auto_approve": "true",
                        },
                    )
                )
            elif reputation.reliability_score < 0.5:
                insights.append(
                    LearningInsight(
                        insight_type="anomaly",
                        supplier_id=reputation.supplier_id,
                        description=(
                            f"{reputation.supplier_name} shows unstable behavior and should stay on HITL review."
                        ),
                        confidence=0.8,
                        suggested_flag_update={f"supplier.{reputation.supplier_id}.force_hitl": "true"},
                    )
                )
            elif reputation.common_issues:
                insights.append(
                    LearningInsight(
                        insight_type="pattern",
                        supplier_id=reputation.supplier_id,
                        description=(
                            f"{reputation.supplier_name} repeatedly triggers: {', '.join(reputation.common_issues)}."
                        ),
                        confidence=0.7,
                        actionable=True,
                    )
                )
        return insights

    def _build_summary(self, reputations: list[SupplierReputation]) -> str:
        if not reputations:
            return "Learning analysis found no supplier history in the selected window."
        reliable = sum(1 for reputation in reputations if reputation.auto_approve_eligible)
        at_risk = sum(1 for reputation in reputations if reputation.reliability_score < 0.5)
        return (
            f"Analyzed {len(reputations)} suppliers. "
            f"{reliable} are auto-approve candidates and {at_risk} require tighter HITL controls."
        )

    async def _generate_report_with_agent(self, payload: dict[str, Any]) -> LearningReport | None:
        result: Any
        if self.agent_runner is not None:
            result = self.agent_runner(payload)
            if asyncio.iscoroutine(result):
                result = await result
            return _coerce_report(result)

        if self.agent is None:
            self.agent = self._create_agent()
        workflow = SequentialBuilder(participants=[self.agent]).build()
        run_result = workflow.run(payload)
        resolved = await run_result if hasattr(run_result, "__await__") else run_result
        if hasattr(resolved, "__aiter__"):
            latest_payload: Any = None
            async for event in resolved:
                latest_payload = getattr(event, "data", event)
            return _coerce_report(latest_payload)
        return _coerce_report(getattr(resolved, "text", resolved))

    def _create_agent(self) -> Any:
        credential = self.config.create_credential()
        gpt5_client, gpt5_mini_client = create_clients(self.config.azure_ai_project_endpoint, credential)
        self._owned_clients.extend([gpt5_client, gpt5_mini_client])
        return create_agents(gpt5_client, gpt5_mini_client)["learning"]


async def run_learning_cycle(config: LearningConfig | None = None) -> LearningReport:
    analyzer = LearningAnalyzer(config=config)
    try:
        return await analyzer.analyze()
    finally:
        await analyzer.close()


def _coerce_report(payload: Any) -> LearningReport | None:
    if payload is None:
        return None
    if isinstance(payload, LearningReport):
        return payload
    try:
        if isinstance(payload, str):
            return LearningReport.model_validate_json(payload)
        return LearningReport.model_validate(payload)
    except Exception:
        return None


def _extract_supplier_id(record: dict[str, Any]) -> str | None:
    for candidate in (
        record.get("supplier_id"),
        record.get("vendor_number"),
        record.get("vendorNumber"),
        _extract_nested(record, "pipeline_result", "extraction", "header", "supplier_tax_id"),
        _extract_nested(record, "pipeline_result", "triage", "supplier_id"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _extract_supplier_name(record: dict[str, Any]) -> str | None:
    for candidate in (
        record.get("supplier_name"),
        record.get("vendor_name"),
        record.get("vendorName"),
        _extract_nested(record, "pipeline_result", "extraction", "header", "supplier_name"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _extract_discrepancies(record: dict[str, Any]) -> list[str]:
    for candidate in (
        record.get("discrepancies"),
        _extract_nested(record, "pipeline_result", "validation", "discrepancies"),
    ):
        if isinstance(candidate, list):
            return [str(item) for item in candidate if str(item).strip()]
    return []


def _extract_nested(record: dict[str, Any], *keys: str) -> Any:
    current: Any = record
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


__all__ = ["CosmosLearningStore", "LearningAnalyzer", "run_learning_cycle"]
