from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from agent_framework import SequentialBuilder

from src.agents.factory import create_agents, create_clients
from src.mcp.bc_mcp.client import BCMCPClient
from src.models.reconciliation import DriftItem, DriftType, ReconciliationReport

from .config import ReconciliationConfig, get_reconciliation_config
from .report_sender import ReconciliationReportSender


class CosmosReconciliationStore:
    def __init__(self, config: ReconciliationConfig) -> None:
        self._config = config
        self._client: Any | None = None

    async def list_processed_records(self, *, since: datetime) -> list[dict[str, Any]]:
        container = await self._get_container()
        query = (
            "SELECT TOP @limit * FROM c WHERE "
            "(IS_DEFINED(c.created_at) AND c.created_at >= @since) OR "
            "(IS_DEFINED(c.updated_at) AND c.updated_at >= @since) OR "
            "(IS_DEFINED(c.last_updated) AND c.last_updated >= @since) "
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
                raise RuntimeError("azure-cosmos is required for the reconciliation store.") from exc
            self._client = CosmosClient(self._config.cosmos_endpoint, credential=self._config.create_credential())
        database = self._client.get_database_client(self._config.database_name)
        return database.get_container_client(self._config.processing_container_name)


class Reconciler:
    def __init__(
        self,
        config: ReconciliationConfig | None = None,
        *,
        review_store: Any | None = None,
        bc_client: BCMCPClient | Any | None = None,
        report_sender: ReconciliationReportSender | None = None,
        agent: Any | None = None,
        agent_runner: Callable[[dict[str, Any]], Any] | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.config = config or get_reconciliation_config()
        self.review_store = review_store or CosmosReconciliationStore(self.config)
        self.bc_client = bc_client or BCMCPClient(credential=self.config.create_credential())
        self.report_sender = report_sender or ReconciliationReportSender(self.config.report_recipients)
        self.agent = agent
        self.agent_runner = agent_runner
        self.now_provider = now_provider or (lambda: datetime.now(tz=UTC))
        self._owned_clients: list[Any] = []

    async def run(self) -> ReconciliationReport:
        now = self.now_provider()
        since = now - timedelta(hours=self.config.reconciliation_window_hours)
        cosmos_records = await self.review_store.list_processed_records(since=since)
        bc_records = await self._list_bc_records(since=since)
        candidate_drifts = self._build_candidate_drifts(cosmos_records=cosmos_records, bc_records=bc_records)
        report = await self._build_report(
            report_date=now.date(),
            cosmos_records=cosmos_records,
            bc_records=bc_records,
            candidate_drifts=candidate_drifts,
        )
        fix_proposals = self.propose_fixes(report)
        self.report_sender.send_report(report, fix_proposals=fix_proposals)
        return report

    async def close(self) -> None:
        if hasattr(self.review_store, "close"):
            maybe_close = self.review_store.close()
            if asyncio.iscoroutine(maybe_close):
                await maybe_close
        for client in self._owned_clients:
            if hasattr(client, "close"):
                maybe_close = client.close()
                if asyncio.iscoroutine(maybe_close):
                    await maybe_close

    def propose_fixes(self, report: ReconciliationReport) -> list[str]:
        return [
            f"Repost candidate for {item.albaran_id} ({item.supplier_name or 'unknown supplier'}) pending HITL approval."
            for item in report.drift_items
            if item.suggested_action == "repost"
        ]

    async def _list_bc_records(self, *, since: datetime) -> list[dict[str, Any]]:
        receipts = await self.bc_client.list_purchase_receipts(top=self.config.query_batch_size)
        filtered: list[dict[str, Any]] = []
        for receipt in receipts:
            payload = receipt.model_dump(mode="json") if hasattr(receipt, "model_dump") else dict(receipt)
            posting_date = _parse_date(payload.get("postingDate"))
            if posting_date is None or posting_date < since.date():
                continue
            filtered.append(payload)
        return filtered

    def _build_candidate_drifts(
        self,
        *,
        cosmos_records: list[dict[str, Any]],
        bc_records: list[dict[str, Any]],
    ) -> list[DriftItem]:
        cosmos_by_id = {
            albaran_id: record for record in cosmos_records if (albaran_id := _extract_cosmos_albaran_id(record))
        }
        bc_by_id = {albaran_id: record for record in bc_records if (albaran_id := _extract_bc_albaran_id(record))}
        drift_items: list[DriftItem] = []

        for albaran_id, cosmos_record in cosmos_by_id.items():
            bc_record = bc_by_id.get(albaran_id)
            if bc_record is None:
                drift_items.append(
                    DriftItem(
                        albaran_id=albaran_id,
                        supplier_name=_extract_cosmos_supplier_name(cosmos_record),
                        drift_type=DriftType.MISSING_IN_BC,
                        cosmos_total=_extract_cosmos_total(cosmos_record),
                        cosmos_status=_extract_cosmos_status(cosmos_record),
                        suggested_action=_suggest_action(
                            DriftType.MISSING_IN_BC,
                            cosmos_status=_extract_cosmos_status(cosmos_record),
                        ),
                    )
                )
                continue

            cosmos_total = _extract_cosmos_total(cosmos_record)
            bc_total = _extract_bc_total(bc_record)
            if cosmos_total is not None and bc_total is not None:
                difference = round(cosmos_total - bc_total, 2)
                if abs(difference) > self.config.amount_tolerance:
                    drift_items.append(
                        DriftItem(
                            albaran_id=albaran_id,
                            supplier_name=_extract_cosmos_supplier_name(cosmos_record)
                            or _extract_bc_supplier_name(bc_record),
                            drift_type=DriftType.AMOUNT_MISMATCH,
                            cosmos_total=cosmos_total,
                            bc_total=bc_total,
                            difference=difference,
                            cosmos_status=_extract_cosmos_status(cosmos_record),
                            bc_status=_extract_bc_status(bc_record),
                            suggested_action=_suggest_action(DriftType.AMOUNT_MISMATCH, difference=difference),
                        )
                    )

            cosmos_status = _extract_cosmos_status(cosmos_record)
            bc_status = _extract_bc_status(bc_record)
            if cosmos_status and bc_status and cosmos_status.casefold() != bc_status.casefold():
                drift_items.append(
                    DriftItem(
                        albaran_id=albaran_id,
                        supplier_name=_extract_cosmos_supplier_name(cosmos_record)
                        or _extract_bc_supplier_name(bc_record),
                        drift_type=DriftType.STATUS_MISMATCH,
                        cosmos_total=cosmos_total,
                        bc_total=bc_total,
                        difference=(
                            round((cosmos_total or 0.0) - (bc_total or 0.0), 2)
                            if cosmos_total is not None and bc_total is not None
                            else None
                        ),
                        cosmos_status=cosmos_status,
                        bc_status=bc_status,
                        suggested_action=_suggest_action(DriftType.STATUS_MISMATCH),
                    )
                )

        for albaran_id, bc_record in bc_by_id.items():
            if albaran_id in cosmos_by_id:
                continue
            drift_items.append(
                DriftItem(
                    albaran_id=albaran_id,
                    supplier_name=_extract_bc_supplier_name(bc_record),
                    drift_type=DriftType.MISSING_IN_COSMOS,
                    bc_total=_extract_bc_total(bc_record),
                    bc_status=_extract_bc_status(bc_record),
                    suggested_action=_suggest_action(DriftType.MISSING_IN_COSMOS),
                )
            )

        return drift_items

    async def _build_report(
        self,
        *,
        report_date: date,
        cosmos_records: list[dict[str, Any]],
        bc_records: list[dict[str, Any]],
        candidate_drifts: list[DriftItem],
    ) -> ReconciliationReport:
        generated = await self._generate_report_with_agent(
            {
                "report_date": report_date.isoformat(),
                "total_cosmos_records": len(cosmos_records),
                "total_bc_records": len(bc_records),
                "candidate_drifts": [item.model_dump(mode="json") for item in candidate_drifts],
                "cosmos_records": cosmos_records,
                "bc_records": bc_records,
            }
        )
        drift_items = generated.drift_items if generated is not None and generated.drift_items else candidate_drifts
        auto_fixable = sum(1 for item in drift_items if item.suggested_action == "repost")
        needs_review = sum(1 for item in drift_items if item.suggested_action in {"investigate", "hitl_review"})
        summary = generated.summary if generated is not None else _build_fallback_summary(drift_items)
        return ReconciliationReport(
            report_date=report_date,
            total_cosmos_records=len(cosmos_records),
            total_bc_records=len(bc_records),
            drifts_found=len(drift_items),
            drift_items=drift_items,
            auto_fixable=auto_fixable,
            needs_review=needs_review,
            summary=summary,
        )

    async def _generate_report_with_agent(self, payload: dict[str, Any]) -> ReconciliationReport | None:
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
        return create_agents(gpt5_client, gpt5_mini_client)["reconciliation"]


async def run_reconciliation_cycle(config: ReconciliationConfig | None = None) -> ReconciliationReport:
    reconciler = Reconciler(config=config)
    try:
        return await reconciler.run()
    finally:
        await reconciler.close()


def _coerce_report(payload: Any) -> ReconciliationReport | None:
    if payload is None:
        return None
    if isinstance(payload, ReconciliationReport):
        return payload
    try:
        if isinstance(payload, str):
            return ReconciliationReport.model_validate_json(payload)
        return ReconciliationReport.model_validate(payload)
    except Exception:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value.strip():
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def _parse_date(value: Any) -> date | None:
    parsed = _parse_datetime(value)
    if parsed is not None:
        return parsed.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        return date.fromisoformat(value)
    return None


def _extract_nested(record: dict[str, Any], *keys: str) -> Any:
    current: Any = record
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_cosmos_albaran_id(record: dict[str, Any]) -> str | None:
    candidates = (
        record.get("albaran_id"),
        record.get("document_number"),
        _extract_nested(record, "pipeline_result", "extraction", "header", "document_number"),
        _extract_nested(record, "pipeline_result", "validation", "po_number"),
        record.get("id"),
    )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _extract_bc_albaran_id(record: dict[str, Any]) -> str | None:
    for key in ("vendorShipmentNo", "externalDocumentNumber", "documentNumber", "orderNumber", "number", "id"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_cosmos_supplier_name(record: dict[str, Any]) -> str | None:
    for candidate in (
        record.get("supplier_name"),
        _extract_nested(record, "pipeline_result", "extraction", "header", "supplier_name"),
        _extract_nested(record, "metadata", "supplier_name"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _extract_bc_supplier_name(record: dict[str, Any]) -> str | None:
    value = record.get("vendorName")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _extract_cosmos_total(record: dict[str, Any]) -> float | None:
    for candidate in (
        record.get("total_amount"),
        _extract_nested(record, "metadata", "total_amount"),
        _extract_nested(record, "pipeline_result", "extraction", "header", "total_amount"),
    ):
        try:
            return None if candidate is None else float(candidate)
        except (TypeError, ValueError):
            continue
    return None


def _extract_bc_total(record: dict[str, Any]) -> float | None:
    for key in ("totalAmount", "total", "amountIncludingVat", "amountIncludingVAT", "invoiceAmount"):
        candidate = record.get(key)
        try:
            return None if candidate is None else float(candidate)
        except (TypeError, ValueError):
            continue
    return None


def _extract_cosmos_status(record: dict[str, Any]) -> str | None:
    for candidate in (record.get("status"), _extract_nested(record, "pipeline_result", "inventory", "success")):
        if isinstance(candidate, bool):
            return "posted" if candidate else "failed"
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _extract_bc_status(record: dict[str, Any]) -> str | None:
    value = record.get("status") or "posted"
    return value.strip() if isinstance(value, str) and value.strip() else None


def _suggest_action(
    drift_type: DriftType,
    *,
    cosmos_status: str | None = None,
    difference: float | None = None,
) -> str:
    if drift_type is DriftType.MISSING_IN_BC:
        return (
            "repost" if (cosmos_status or "").casefold() in {"approved", "posted", "ready_to_post"} else "hitl_review"
        )
    if drift_type is DriftType.MISSING_IN_COSMOS:
        return "investigate"
    if drift_type is DriftType.AMOUNT_MISMATCH:
        return "ignore" if difference is not None and abs(difference) <= 0.01 else "hitl_review"
    return "investigate"


def _build_fallback_summary(drift_items: list[DriftItem]) -> str:
    if not drift_items:
        return "Reconciliation completed successfully with no drifts detected."
    drift_counts: dict[DriftType, int] = dict.fromkeys(DriftType, 0)
    for item in drift_items:
        drift_counts[item.drift_type] += 1
    return (
        "Reconciliation found "
        f"{len(drift_items)} drifts: {drift_counts[DriftType.MISSING_IN_BC]} missing in BC, "
        f"{drift_counts[DriftType.MISSING_IN_COSMOS]} missing in Cosmos, "
        f"{drift_counts[DriftType.AMOUNT_MISMATCH]} amount mismatches, and "
        f"{drift_counts[DriftType.STATUS_MISMATCH]} status mismatches."
    )


__all__ = ["CosmosReconciliationStore", "Reconciler", "run_reconciliation_cycle"]
