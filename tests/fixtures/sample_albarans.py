from __future__ import annotations

from datetime import date

from src.models import (
    AlbaranExtraction,
    AlbaranHeader,
    CoherenceCheckResult,
    DocumentType,
    LineComparison,
    LineItem,
    PostingLineItem,
    PostingResult,
    PurchaseReceiptPosting,
    TriageResult,
    ValidationResult,
)


def sample_albaran_header(
    *,
    supplier_name: str = "Herstera Garden",
    supplier_tax_id: str | None = "B12345678",
    document_type: DocumentType = DocumentType.ALBARAN,
    document_number: str = "ALB-2026-0001",
    document_date: date | None = date(2026, 1, 15),
    delivery_date: date | None = date(2026, 1, 16),
    purchase_order_number: str | None = "PO-2026-0456",
    store_name: str | None = "Verdecora Málaga",
    total_amount: float | None = 54.0,
    currency: str = "EUR",
) -> AlbaranHeader:
    return AlbaranHeader(
        supplier_name=supplier_name,
        supplier_tax_id=supplier_tax_id,
        document_type=document_type,
        document_number=document_number,
        document_date=document_date,
        delivery_date=delivery_date,
        purchase_order_number=purchase_order_number,
        store_name=store_name,
        total_amount=total_amount,
        currency=currency,
    )


def sample_line_items(*, supplier_name: str = "Herstera Garden") -> list[LineItem]:
    if supplier_name == "Royal Canin":
        return [
            LineItem(
                line_number=1,
                product_code="RC-MEDIUM-12KG",
                ean_code="3182550708183",
                description="Royal Canin Medium Adult 12kg",
                quantity=2.0,
                unit_price=49.5,
                discount_pct=5.0,
                total=94.05,
            ),
            LineItem(
                line_number=2,
                product_code="RC-MAXI-15KG",
                ean_code="3182550402142",
                description="Royal Canin Maxi Adult 15kg",
                quantity=1.0,
                unit_price=58.0,
                total=58.0,
            ),
        ]

    if supplier_name == "FANSA":
        return [
            LineItem(
                line_number=1,
                product_code="FAN-001",
                description="Fertilizante universal 5L",
                quantity=4.0,
                unit_price=7.5,
                total=30.0,
                lot_number="LOT-FAN-01",
            ),
            LineItem(
                line_number=2,
                product_code="FAN-002",
                description="Sustrato premium 50L",
                quantity=2.0,
                unit_price=9.75,
                total=19.5,
            ),
        ]

    return [
        LineItem(
            line_number=1,
            product_code="HER-001",
            ean_code="8437001234567",
            description="Maceta cerámica 20cm",
            quantity=3.0,
            unit_price=8.0,
            total=24.0,
        ),
        LineItem(
            line_number=2,
            product_code="HER-002",
            ean_code="8437007654321",
            description="Jardinera exterior 60cm",
            quantity=2.0,
            unit_price=15.0,
            total=30.0,
            expiry_date=date(2026, 12, 31),
        ),
    ]


def sample_extraction(
    *,
    supplier_name: str = "Herstera Garden",
    confidence_score: float = 0.96,
    extraction_warnings: list[str] | None = None,
    source_pages: list[int] | None = None,
    raw_text: str | None = "ALBARAN DE ENTREGA",
    line_items: list[LineItem] | None = None,
) -> AlbaranExtraction:
    items = line_items if line_items is not None else sample_line_items(supplier_name=supplier_name)
    return AlbaranExtraction(
        header=sample_albaran_header(
            supplier_name=supplier_name,
            total_amount=sum(item.total or 0.0 for item in items),
        ),
        line_items=items,
        raw_text=raw_text,
        confidence_score=confidence_score,
        extraction_warnings=list(extraction_warnings or []),
        source_pages=list(source_pages or [1]),
    )


def sample_triage_result(
    *,
    document_type: DocumentType = DocumentType.ALBARAN,
    language: str = "es",
    supplier_id: str | None = "HERSTERA",
    confidence: float = 0.94,
    routing_decision: str = "extract",
    reasoning: str = "Contiene palabras clave de albarán y datos de proveedor.",
) -> TriageResult:
    return TriageResult(
        document_type=document_type,
        language=language,
        supplier_id=supplier_id,
        confidence=confidence,
        routing_decision=routing_decision,
        reasoning=reasoning,
    )


def sample_coherence_result(
    *,
    is_coherent: bool = True,
    overall_confidence: float = 0.91,
    header_issues: list[str] | None = None,
    line_item_issues: list[str] | None = None,
    bc_match_found: bool = True,
    matched_po_number: str | None = "PO-2026-0456",
    suggested_corrections: dict[str, str] | None = None,
) -> CoherenceCheckResult:
    return CoherenceCheckResult(
        is_coherent=is_coherent,
        overall_confidence=overall_confidence,
        header_issues=list(header_issues or []),
        line_item_issues=list(line_item_issues or []),
        bc_match_found=bc_match_found,
        matched_po_number=matched_po_number,
        suggested_corrections=dict(suggested_corrections or {}),
    )


def sample_herstera_extraction() -> AlbaranExtraction:
    return sample_extraction(supplier_name="Herstera Garden")


def sample_fansa_extraction() -> AlbaranExtraction:
    return sample_extraction(supplier_name="FANSA")


def sample_validation_result(
    *,
    is_valid: bool = True,
    overall_match_pct: float = 0.98,
    recommendation: str = "approve",
    po_found: bool = True,
    po_number: str | None = "PO-2026-0456",
    discrepancies: list[str] | None = None,
) -> ValidationResult:
    return ValidationResult(
        is_valid=is_valid,
        overall_match_pct=overall_match_pct,
        line_comparisons=[
            LineComparison(
                line_number=1,
                field="quantity",
                extracted_value="3.0",
                bc_value="3.0",
                difference_pct=0.0,
                status="match",
            )
        ],
        header_match=True,
        po_found=po_found,
        po_number=po_number,
        total_lines_matched=2,
        total_lines_mismatched=0 if is_valid else 1,
        total_lines_within_tolerance=0,
        discrepancies=list(discrepancies or []),
        recommendation=recommendation,
        reasoning="Line items align with the purchase order.",
    )


def sample_purchase_receipt_posting() -> PurchaseReceiptPosting:
    return PurchaseReceiptPosting(
        vendor_number="HERSTERA",
        purchase_order_number="PO-2026-0456",
        posting_date=date(2026, 1, 16),
        line_items=[
            PostingLineItem(
                item_number="HER-001",
                description="Maceta cerámica 20cm",
                quantity=3.0,
                unit_cost=8.0,
                line_amount=24.0,
            )
        ],
        total_amount=24.0,
    )


def sample_posting_result(
    *,
    success: bool = True,
    receipt_number: str | None = "RCPT-2026-0012",
    posted_lines: int = 2,
    errors: list[str] | None = None,
) -> PostingResult:
    return PostingResult(
        success=success,
        receipt_number=receipt_number,
        posted_lines=posted_lines,
        errors=list(errors or []),
        bc_document_url="https://businesscentral/purchaseReceipts/RCPT-2026-0012" if receipt_number else None,
    )


def sample_royal_canin_extraction() -> AlbaranExtraction:
    return sample_extraction(supplier_name="Royal Canin")


def sample_multi_page_extraction() -> AlbaranExtraction:
    return sample_extraction(
        supplier_name="Royal Canin",
        confidence_score=0.88,
        extraction_warnings=["Page 2 contains faint handwriting."],
        source_pages=[1, 2],
        raw_text="ALBARAN PAGE 1\nALBARAN PAGE 2",
    )


__all__ = [
    "sample_albaran_header",
    "sample_line_items",
    "sample_extraction",
    "sample_triage_result",
    "sample_coherence_result",
    "sample_validation_result",
    "sample_purchase_receipt_posting",
    "sample_posting_result",
    "sample_herstera_extraction",
    "sample_fansa_extraction",
    "sample_royal_canin_extraction",
    "sample_multi_page_extraction",
]
