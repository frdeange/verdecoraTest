from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class DriftType(str, Enum):
    MISSING_IN_BC = "missing_in_bc"
    MISSING_IN_COSMOS = "missing_in_cosmos"
    AMOUNT_MISMATCH = "amount_mismatch"
    STATUS_MISMATCH = "status_mismatch"


class DriftItem(BaseModel):
    albaran_id: str
    supplier_name: str | None = None
    drift_type: DriftType
    cosmos_total: float | None = None
    bc_total: float | None = None
    difference: float | None = None
    cosmos_status: str | None = None
    bc_status: str | None = None
    suggested_action: str


class ReconciliationReport(BaseModel):
    report_date: date
    total_cosmos_records: int
    total_bc_records: int
    drifts_found: int
    drift_items: list[DriftItem] = Field(default_factory=list)
    auto_fixable: int = 0
    needs_review: int = 0
    summary: str
