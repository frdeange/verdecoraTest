from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from src.agents.prompts import build_reconciliation_instructions
from src.models.reconciliation import DriftItem, DriftType, ReconciliationReport
from src.services.reconciliation.config import ReconciliationConfig
from src.services.reconciliation.reconciler import Reconciler

pytestmark = pytest.mark.unit


class FakeReviewStore:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = records

    async def list_processed_records(self, *, since: datetime) -> list[dict[str, Any]]:
        return list(self._records)

    async def close(self) -> None:
        return None


class FakeBCClient:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = records

    async def list_purchase_receipts(self, *, top: int = 50) -> list[dict[str, Any]]:
        return list(self._records[:top])


class RecordingSender:
    def __init__(self) -> None:
        self.sent_reports: list[ReconciliationReport] = []
        self.fixes: list[list[str]] = []

    def send_report(self, report: ReconciliationReport, *, fix_proposals: list[str] | None = None) -> None:
        self.sent_reports.append(report)
        self.fixes.append(list(fix_proposals or []))


def test_build_reconciliation_instructions_embeds_schema() -> None:
    instructions = build_reconciliation_instructions(("cosmos.query_documents",))

    assert "A7 reconciliation agent" in instructions
    assert '"drift_items"' in instructions
    assert "cosmos.query_documents" in instructions


def test_reconciliation_report_model_round_trip() -> None:
    report = ReconciliationReport(
        report_date=datetime(2026, 5, 5, tzinfo=UTC).date(),
        total_cosmos_records=1,
        total_bc_records=2,
        drifts_found=1,
        drift_items=[
            DriftItem(
                albaran_id="ALB-2",
                supplier_name="FANSA",
                drift_type=DriftType.MISSING_IN_COSMOS,
                bc_total=80.0,
                suggested_action="investigate",
            )
        ],
        auto_fixable=0,
        needs_review=1,
        summary="One mismatch.",
    )

    assert ReconciliationReport.model_validate(report.model_dump(mode="json")) == report


@pytest.mark.asyncio
async def test_reconciler_detects_missing_records_and_sends_report() -> None:
    now = datetime(2026, 5, 5, 6, 0, tzinfo=UTC)
    sender = RecordingSender()
    cosmos_records = [
        {
            "id": "record-1",
            "document_number": "ALB-1",
            "supplier_name": "Herstera Garden",
            "total_amount": 100.0,
            "status": "posted",
            "created_at": now.isoformat(),
        },
        {
            "id": "record-2",
            "document_number": "ALB-2",
            "supplier_name": "FANSA",
            "total_amount": 50.0,
            "status": "approved",
            "created_at": now.isoformat(),
        },
    ]
    bc_records = [
        {
            "vendorShipmentNo": "ALB-1",
            "vendorName": "Herstera Garden",
            "postingDate": now.date().isoformat(),
            "status": "posted",
            "totalAmount": 100.0,
        },
        {
            "vendorShipmentNo": "ALB-3",
            "vendorName": "Royal Canin",
            "postingDate": now.date().isoformat(),
            "status": "posted",
            "totalAmount": 80.0,
        },
    ]

    async def fake_agent_runner(payload: dict[str, Any]) -> ReconciliationReport:
        drift_items = [DriftItem.model_validate(item) for item in payload["candidate_drifts"]]
        return ReconciliationReport(
            report_date=now.date(),
            total_cosmos_records=payload["total_cosmos_records"],
            total_bc_records=payload["total_bc_records"],
            drifts_found=len(drift_items),
            drift_items=drift_items,
            auto_fixable=1,
            needs_review=1,
            summary="Agent confirmed one repost and one investigation.",
        )

    reconciler = Reconciler(
        config=ReconciliationConfig(report_recipients=("ops@verdecora.example.com",)),
        review_store=FakeReviewStore(cosmos_records),
        bc_client=FakeBCClient(bc_records),
        report_sender=sender,
        agent_runner=fake_agent_runner,
        now_provider=lambda: now,
    )

    report = await reconciler.run()

    assert report.drifts_found == 2
    assert {item.drift_type for item in report.drift_items} == {
        DriftType.MISSING_IN_BC,
        DriftType.MISSING_IN_COSMOS,
    }
    assert report.auto_fixable == 1
    assert report.needs_review == 1
    assert sender.sent_reports[0] == report
    assert any("ALB-2" in fix for fix in sender.fixes[0])
