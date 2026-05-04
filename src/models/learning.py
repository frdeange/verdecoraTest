from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SupplierReputation(BaseModel):
    supplier_id: str
    supplier_name: str
    total_albaranes_processed: int = 0
    success_rate: float = Field(ge=0.0, le=1.0, default=1.0)
    avg_discrepancy_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    common_issues: list[str] = Field(default_factory=list)
    avg_processing_time_seconds: float | None = None
    reliability_score: float = Field(ge=0.0, le=1.0, default=0.5)
    last_updated: datetime | None = None
    recommended_tolerance_pct: float = 2.0
    auto_approve_eligible: bool = False
    notes: str | None = None


class LearningInsight(BaseModel):
    insight_type: str
    supplier_id: str | None = None
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    actionable: bool = True
    suggested_flag_update: dict[str, str] | None = None


class LearningReport(BaseModel):
    report_date: datetime
    suppliers_analyzed: int
    insights: list[LearningInsight] = Field(default_factory=list)
    reputation_updates: list[SupplierReputation] = Field(default_factory=list)
    feature_flag_proposals: list[dict[str, str]] = Field(default_factory=list)
    summary: str
