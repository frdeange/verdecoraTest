from __future__ import annotations

import pytest

from src.models.validation import ValidationResult, compare_line_values
from tests.fixtures.sample_validations import sample_line_comparison, sample_validation

pytestmark = pytest.mark.unit


def test_line_comparison_serializes_round_trip() -> None:
    comparison = sample_line_comparison(status="tolerance", difference_pct=1.75)

    restored = type(comparison).model_validate(comparison.model_dump(mode="json"))

    assert restored == comparison
    assert restored.status == "tolerance"
    assert restored.difference_pct == 1.75


def test_validation_result_serializes_with_empty_comparisons() -> None:
    validation = ValidationResult(
        is_valid=False,
        overall_match_pct=0.8,
        tolerance_pct=0.0,
        line_comparisons=[],
        header_match=False,
        po_found=False,
        po_number=None,
        total_lines_matched=0,
        total_lines_mismatched=0,
        total_lines_within_tolerance=0,
        discrepancies=["Manual review required."],
        recommendation="hitl_review",
        reasoning="No comparisons were available.",
    )

    restored = ValidationResult.model_validate(validation.model_dump(mode="json"))

    assert restored == validation
    assert restored.line_comparisons == []
    assert restored.tolerance_pct == 0.0


def test_compare_line_values_uses_zero_tolerance_as_strict_match() -> None:
    comparison = compare_line_values(
        line_number=3,
        field="unit_price",
        extracted_value=10.01,
        bc_value=10.0,
        tolerance_pct=0.0,
    )

    assert comparison.status == "mismatch"
    assert comparison.difference_pct == pytest.approx(0.1)


def test_sample_validation_round_trip() -> None:
    validation = sample_validation()

    restored = ValidationResult.model_validate(validation.model_dump(mode="json"))

    assert restored == validation
    assert restored.line_comparisons[0].status == "match"
