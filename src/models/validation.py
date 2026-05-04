from __future__ import annotations

from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, Field

APPROVAL_MATCH_THRESHOLD = 0.95
HITL_REVIEW_THRESHOLD = 0.80
DEFAULT_TOLERANCE_PCT = 2.0


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
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT
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


def _to_decimal(value: str | float | int | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def calculate_difference_pct(
    extracted_value: str | float | int | None, bc_value: str | float | int | None
) -> float | None:
    extracted_decimal = _to_decimal(extracted_value)
    bc_decimal = _to_decimal(bc_value)
    if extracted_decimal is None or bc_decimal is None:
        return None
    if bc_decimal == 0:
        return 0.0 if extracted_decimal == 0 else 100.0
    difference_ratio = abs(extracted_decimal - bc_decimal) / abs(bc_decimal)
    return float(difference_ratio * Decimal("100"))


def compare_line_values(
    *,
    line_number: int,
    field: str,
    extracted_value: str | float | int | None,
    bc_value: str | float | int | None,
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
) -> LineComparison:
    extracted_text = "" if extracted_value is None else str(extracted_value)
    bc_text = "" if bc_value is None else str(bc_value)

    if extracted_value is None and bc_value is not None:
        return LineComparison(
            line_number=line_number,
            field=field,
            extracted_value=extracted_text,
            bc_value=bc_text,
            difference_pct=None,
            status="missing_in_extraction",
        )
    if bc_value is None and extracted_value is not None:
        return LineComparison(
            line_number=line_number,
            field=field,
            extracted_value=extracted_text,
            bc_value=bc_text,
            difference_pct=None,
            status="missing_in_bc",
        )

    difference_pct = calculate_difference_pct(extracted_value, bc_value)
    if extracted_text == bc_text or difference_pct == 0.0:
        status = "match"
    elif difference_pct is not None and difference_pct <= tolerance_pct:
        status = "tolerance"
    else:
        status = "mismatch"

    return LineComparison(
        line_number=line_number,
        field=field,
        extracted_value=extracted_text,
        bc_value=bc_text,
        difference_pct=difference_pct,
        status=status,
    )


def recommend_validation_action(overall_match_pct: float) -> str:
    if overall_match_pct > APPROVAL_MATCH_THRESHOLD:
        return "approve"
    if overall_match_pct >= HITL_REVIEW_THRESHOLD:
        return "hitl_review"
    return "reject"
