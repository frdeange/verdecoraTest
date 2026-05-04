from __future__ import annotations

from typing import Any

from src.models.inventory import PostingResult
from src.models.validation import ValidationResult


def should_process_inventory(validation_result: ValidationResult | dict[str, Any] | None) -> bool:
    if validation_result is None:
        return False
    normalized_result = validation_result
    if not isinstance(validation_result, ValidationResult):
        normalized_result = ValidationResult.model_validate(validation_result)
    return normalized_result.is_valid and normalized_result.recommendation == "approve"


def build_posting_failure_result(
    error: Exception | str,
    *,
    receipt_number: str | None = None,
    posted_lines: int = 0,
    bc_document_url: str | None = None,
) -> PostingResult:
    message = str(error).strip() or "Business Central posting failed."
    return PostingResult(
        success=False,
        receipt_number=receipt_number,
        posted_lines=posted_lines,
        errors=[message],
        bc_document_url=bc_document_url,
    )


__all__ = ["build_posting_failure_result", "should_process_inventory"]
