from __future__ import annotations

from datetime import date

from src.models.inventory import PostingLineItem, PostingResult, PurchaseReceiptPosting
from src.models.validation import LineComparison, ValidationResult


def sample_line_comparison(*, status: str = "match", difference_pct: float | None = 0.0) -> LineComparison:
    return LineComparison(
        line_number=1,
        field="quantity",
        extracted_value="10",
        bc_value="10",
        difference_pct=difference_pct,
        status=status,
    )


def sample_validation(*, overall_match_pct: float = 0.98, recommendation: str = "approve") -> ValidationResult:
    return ValidationResult(
        is_valid=recommendation == "approve",
        overall_match_pct=overall_match_pct,
        line_comparisons=[sample_line_comparison()],
        header_match=True,
        po_found=True,
        po_number="PO-2026-0456",
        total_lines_matched=1,
        total_lines_mismatched=0,
        total_lines_within_tolerance=0,
        discrepancies=[],
        recommendation=recommendation,
        reasoning="Synthetic validation fixture.",
    )


def sample_posting_line_item() -> PostingLineItem:
    return PostingLineItem(
        item_number="HER-001",
        description="Maceta cerámica 20cm",
        quantity=3.0,
        unit_cost=8.0,
        line_amount=24.0,
    )


def sample_purchase_receipt_posting() -> PurchaseReceiptPosting:
    return PurchaseReceiptPosting(
        vendor_number="HERSTERA",
        purchase_order_number="PO-2026-0456",
        posting_date=date(2026, 1, 16),
        document_number="ALB-2026-0001",
        line_items=[sample_posting_line_item()],
        total_amount=24.0,
    )


def sample_posting_result(*, success: bool = True, errors: list[str] | None = None) -> PostingResult:
    return PostingResult(
        success=success,
        receipt_number="RCPT-2026-0012" if success else None,
        posted_lines=1 if success else 0,
        errors=list(errors or []),
        bc_document_url="https://businesscentral/purchaseReceipts/RCPT-2026-0012" if success else None,
    )
