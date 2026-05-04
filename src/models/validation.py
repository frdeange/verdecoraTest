from __future__ import annotations

from pydantic import BaseModel, Field


class LineComparison(BaseModel):
    line_number: int
    field: str
    extracted_value: str
    bc_value: str
    difference_pct: float | None = None
    status: str


class ValidationResult(BaseModel):
    is_valid: bool
    overall_match_pct: float = Field(ge=0.0, le=1.0)
    tolerance_pct: float = 2.0
    line_comparisons: list[LineComparison] = Field(default_factory=list)
    header_match: bool = True
    po_found: bool = False
    po_number: str | None = None
    total_lines_matched: int = 0
    total_lines_mismatched: int = 0
    total_lines_within_tolerance: int = 0
    discrepancies: list[str] = Field(default_factory=list)
    recommendation: str
    reasoning: str
