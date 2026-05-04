from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from src.models import (
    AlbaranExtraction,
    AlbaranHeader,
    CoherenceCheckResult,
    DocumentType,
    DriftItem,
    DriftType,
    LearningInsight,
    LearningReport,
    LineComparison,
    LineItem,
    PostingLineItem,
    PurchaseReceiptPosting,
    ReconciliationReport,
    SupplierReputation,
    TriageResult,
    ValidationResult,
)
from tests.fixtures.sample_albarans import (
    sample_albaran_header,
    sample_coherence_result,
    sample_extraction,
    sample_line_items,
    sample_posting_result,
    sample_purchase_receipt_posting,
    sample_validation_result,
)

pytestmark = pytest.mark.unit


def test_albaran_header_supports_defaults_and_optional_fields() -> None:
    header = AlbaranHeader(
        supplier_name="Herstera Garden",
        document_type=DocumentType.ALBARAN,
        document_number="ALB-2026-0001",
    )

    assert header.currency == "EUR"
    assert header.supplier_tax_id is None
    assert header.document_date is None
    assert header.delivery_date is None
    assert header.purchase_order_number is None
    assert header.store_name is None
    assert header.total_amount is None


def test_albaran_header_allows_empty_strings_and_none_values() -> None:
    header = AlbaranHeader(
        supplier_name="",
        supplier_tax_id=None,
        document_type=DocumentType.UNKNOWN,
        document_number="",
        document_date=None,
        delivery_date=None,
        purchase_order_number=None,
        store_name=None,
        total_amount=None,
    )

    assert header.supplier_name == ""
    assert header.document_number == ""
    assert header.document_type is DocumentType.UNKNOWN


def test_line_item_supports_optional_fields_and_zero_quantity() -> None:
    line_item = LineItem(
        line_number=1,
        product_code="",
        ean_code=None,
        description="",
        quantity=0,
        unit_price=None,
        discount_pct=None,
        total=None,
        lot_number=None,
        expiry_date=None,
    )

    assert line_item.quantity == 0.0
    assert line_item.product_code == ""
    assert line_item.description == ""
    assert line_item.unit_price is None
    assert line_item.expiry_date is None


@pytest.mark.parametrize(
    ("field_name", "value"),
    [("quantity", "abc"), ("unit_price", "invalid"), ("discount_pct", "5%")],
)
def test_line_item_rejects_invalid_numeric_values(field_name: str, value: str) -> None:
    payload: dict[str, object] = {
        "line_number": 1,
        "description": "Maceta",
        "quantity": 2,
        "unit_price": 8.0,
        "discount_pct": 0.0,
    }
    payload[field_name] = value

    with pytest.raises(ValidationError):
        LineItem.model_validate(payload)


def test_albaran_extraction_serializes_and_round_trips() -> None:
    extraction = sample_extraction(source_pages=[1, 2], extraction_warnings=["Unreadable footer"])

    dumped = extraction.model_dump(mode="json")
    restored = AlbaranExtraction.model_validate(dumped)

    assert restored == extraction
    assert dumped["source_pages"] == [1, 2]
    assert dumped["header"]["document_date"] == date(2026, 1, 15).isoformat()
    assert dumped["extraction_warnings"] == ["Unreadable footer"]


@pytest.mark.parametrize("confidence_score", [-0.01, 1.01])
def test_albaran_extraction_requires_confidence_between_zero_and_one(confidence_score: float) -> None:
    with pytest.raises(ValidationError):
        AlbaranExtraction(
            header=sample_albaran_header(),
            line_items=sample_line_items(),
            confidence_score=confidence_score,
        )


@pytest.mark.parametrize(
    ("document_type", "routing_decision"),
    [
        (DocumentType.ALBARAN, "extract"),
        (DocumentType.FACTURA, "manual_review"),
        (DocumentType.PACKING_LIST, "manual_review"),
        (DocumentType.UNKNOWN, "reject"),
    ],
)
def test_triage_result_supports_all_document_types(document_type: DocumentType, routing_decision: str) -> None:
    result = TriageResult(
        document_type=document_type,
        language="es",
        confidence=0.8,
        routing_decision=routing_decision,
        reasoning="Synthetic test payload.",
    )

    assert result.document_type is document_type
    assert result.routing_decision == routing_decision


@pytest.mark.parametrize("confidence", [-0.5, 1.5])
def test_triage_result_rejects_confidence_outside_bounds(confidence: float) -> None:
    with pytest.raises(ValidationError):
        TriageResult(
            document_type=DocumentType.ALBARAN,
            confidence=confidence,
            routing_decision="extract",
            reasoning="Invalid confidence.",
        )


def test_coherence_check_result_defaults_and_issue_lists() -> None:
    result = CoherenceCheckResult(is_coherent=False, overall_confidence=0.45)

    assert result.header_issues == []
    assert result.line_item_issues == []
    assert result.bc_match_found is False
    assert result.matched_po_number is None
    assert result.suggested_corrections == {}


def test_coherence_check_result_serialization_round_trip() -> None:
    coherence = sample_coherence_result(
        is_coherent=False,
        overall_confidence=0.42,
        header_issues=["Supplier not found in BC"],
        line_item_issues=["Line 2 total mismatch"],
        bc_match_found=False,
        matched_po_number=None,
        suggested_corrections={"matched_po_number": "PO-2026-0457"},
    )

    dumped = coherence.model_dump(mode="json")
    restored = CoherenceCheckResult.model_validate(dumped)

    assert restored == coherence
    assert dumped["suggested_corrections"]["matched_po_number"] == "PO-2026-0457"


def test_validation_result_defaults_and_round_trip() -> None:
    validation = sample_validation_result()

    dumped = validation.model_dump(mode="json")
    restored = ValidationResult.model_validate(dumped)

    assert restored == validation
    assert dumped["line_comparisons"][0]["status"] == "match"


@pytest.mark.parametrize("overall_match_pct", [-0.1, 1.1])
def test_validation_result_rejects_match_percentage_outside_bounds(overall_match_pct: float) -> None:
    with pytest.raises(ValidationError):
        ValidationResult(
            is_valid=True,
            overall_match_pct=overall_match_pct,
            recommendation="approve",
            reasoning="Invalid percentage.",
        )


def test_purchase_receipt_posting_round_trip() -> None:
    posting = sample_purchase_receipt_posting()

    dumped = posting.model_dump(mode="json")
    restored = PurchaseReceiptPosting.model_validate(dumped)

    assert restored == posting
    assert dumped["posting_date"] == "2026-01-16"


def test_posting_result_defaults_and_errors() -> None:
    result = sample_posting_result(success=False, receipt_number=None, posted_lines=0, errors=["BC timeout"])

    assert result.success is False
    assert result.receipt_number is None
    assert result.errors == ["BC timeout"]


def test_supporting_models_accept_numeric_values() -> None:
    comparison = LineComparison(
        line_number=1,
        field="price",
        extracted_value="8.00",
        bc_value="8.00",
        difference_pct=0.0,
        status="match",
    )
    posting_line = PostingLineItem(
        item_number="HER-001",
        description="Maceta cerámica 20cm",
        quantity=3,
        unit_cost=8,
        line_amount=24,
    )

    assert comparison.difference_pct == 0.0
    assert posting_line.quantity == 3.0
    assert posting_line.unit_cost == 8.0


def test_reconciliation_report_round_trip() -> None:
    report = ReconciliationReport(
        report_date=date(2026, 5, 5),
        total_cosmos_records=2,
        total_bc_records=2,
        drifts_found=1,
        drift_items=[
            DriftItem(
                albaran_id="ALB-1",
                supplier_name="Herstera Garden",
                drift_type=DriftType.MISSING_IN_BC,
                cosmos_total=100.0,
                suggested_action="repost",
            )
        ],
        auto_fixable=1,
        needs_review=0,
        summary="One BC drift detected.",
    )

    restored = ReconciliationReport.model_validate(report.model_dump(mode="json"))

    assert restored == report
    assert restored.drift_items[0].drift_type is DriftType.MISSING_IN_BC


def test_learning_report_round_trip() -> None:
    report = LearningReport(
        report_date=datetime(2026, 5, 5, 12, 0, tzinfo=UTC),
        suppliers_analyzed=1,
        insights=[
            LearningInsight(
                insight_type="recommendation",
                supplier_id="SUP-1",
                description="Supplier can be auto-approved.",
                confidence=0.95,
                suggested_flag_update={"supplier.SUP-1.auto_approve": "true"},
            )
        ],
        reputation_updates=[
            SupplierReputation(
                supplier_id="SUP-1",
                supplier_name="Supplier 1",
                total_albaranes_processed=4,
                reliability_score=0.96,
                auto_approve_eligible=True,
            )
        ],
        feature_flag_proposals=[{"supplier.SUP-1.auto_approve": "true"}],
        summary="Supplier 1 is reliable.",
    )

    restored = LearningReport.model_validate(report.model_dump(mode="json"))

    assert restored == report
    assert restored.reputation_updates[0].auto_approve_eligible is True
