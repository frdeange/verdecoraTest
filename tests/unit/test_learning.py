from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from src.agents.prompts import build_learning_instructions
from src.models.learning import LearningReport
from src.services.learning.analyzer import LearningAnalyzer
from src.services.learning.config import LearningConfig

pytestmark = pytest.mark.unit


class FakeHistoryStore:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = records

    async def list_processed_records(self, *, since: datetime) -> list[dict[str, Any]]:
        return list(self._records)

    async def close(self) -> None:
        return None


def test_build_learning_instructions_embeds_schema() -> None:
    instructions = build_learning_instructions(("feature_flags.set_supplier_config",))

    assert "A8 learning agent" in instructions
    assert '"reputation_updates"' in instructions
    assert "feature_flags.set_supplier_config" in instructions


def test_learning_report_model_round_trip() -> None:
    now = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)
    report = LearningReport(
        report_date=now,
        suppliers_analyzed=0,
        summary="No data available.",
    )

    assert LearningReport.model_validate(report.model_dump(mode="json")) == report


@pytest.mark.asyncio
async def test_learning_analyzer_updates_reputations_and_applies_flags() -> None:
    now = datetime(2026, 5, 11, 4, 0, tzinfo=UTC)
    created = now - timedelta(minutes=10)
    supplier_configs: list[dict[str, Any]] = []
    flags: list[dict[str, str]] = []
    records = [
        {
            "supplier_id": "SUP-1",
            "supplier_name": "Reliable Supplier",
            "status": "posted",
            "discrepancies": [],
            "total_lines": 2,
            "has_signature": True,
            "created_at": created.isoformat(),
            "completed_at": now.isoformat(),
        },
        {
            "supplier_id": "SUP-1",
            "supplier_name": "Reliable Supplier",
            "status": "posted",
            "discrepancies": [],
            "total_lines": 3,
            "has_signature": True,
            "created_at": created.isoformat(),
            "completed_at": now.isoformat(),
        },
        {
            "supplier_id": "SUP-1",
            "supplier_name": "Reliable Supplier",
            "status": "posted",
            "discrepancies": [],
            "total_lines": 1,
            "has_signature": True,
            "created_at": created.isoformat(),
            "completed_at": now.isoformat(),
        },
        {
            "supplier_id": "SUP-2",
            "supplier_name": "Risky Supplier",
            "status": "failed",
            "discrepancies": ["amount mismatch"],
            "total_lines": 1,
            "has_signature": False,
            "created_at": created.isoformat(),
            "completed_at": now.isoformat(),
        },
    ]

    def record_supplier_config(
        *, supplier_id: str, configuration: dict[str, Any], description: str | None = None
    ) -> dict[str, Any]:
        supplier_configs.append(
            {"supplier_id": supplier_id, "configuration": configuration, "description": description}
        )
        return {"supplier_id": supplier_id, "configuration": configuration}

    def record_flag(*, flag_name: str, value: Any, description: str | None = None) -> dict[str, Any]:
        flags.append({"flag_name": flag_name, "value": str(value), "description": description or ""})
        return {"flag_name": flag_name, "value": value}

    analyzer = LearningAnalyzer(
        config=LearningConfig(apply_feature_flag_proposals=True),
        history_store=FakeHistoryStore(records),
        agent_runner=lambda payload: None,
        set_supplier_config_tool=record_supplier_config,
        set_flag_tool=record_flag,
        now_provider=lambda: now,
    )

    report = await analyzer.analyze()

    assert report.suppliers_analyzed == 2
    assert len(report.reputation_updates) == 2
    assert any(rep.supplier_id == "SUP-1" and rep.auto_approve_eligible for rep in report.reputation_updates)
    assert any(rep.supplier_id == "SUP-2" for rep in report.reputation_updates)
    assert len(supplier_configs) == 2
    assert any(entry["supplier_id"] == "SUP-1" for entry in supplier_configs)
    assert any(flag["flag_name"] == "supplier.SUP-1.auto_approve" for flag in flags)
    assert any(flag["flag_name"] == "supplier.SUP-2.force_hitl" for flag in flags)
    assert "Analyzed 2 suppliers" in report.summary
