from __future__ import annotations

import pytest

from src.models.inventory import PostingLineItem, PostingResult, PurchaseReceiptPosting
from tests.fixtures.sample_validations import (
    sample_posting_line_item,
    sample_posting_result,
    sample_purchase_receipt_posting,
)

pytestmark = pytest.mark.unit


def test_posting_line_item_round_trip() -> None:
    line_item = sample_posting_line_item()

    restored = PostingLineItem.model_validate(line_item.model_dump(mode="json"))

    assert restored == line_item
    assert restored.line_amount == 24.0


def test_purchase_receipt_posting_round_trip() -> None:
    posting = sample_purchase_receipt_posting()

    restored = PurchaseReceiptPosting.model_validate(posting.model_dump(mode="json"))

    assert restored == posting
    assert restored.document_number == "ALB-2026-0001"


def test_posting_result_round_trip() -> None:
    result = sample_posting_result(success=True)

    restored = PostingResult.model_validate(result.model_dump(mode="json"))

    assert restored == result
    assert restored.posted_lines == 1


def test_posting_line_item_accepts_integer_inputs() -> None:
    line_item = PostingLineItem(
        item_number="HER-001",
        description="Maceta cerámica 20cm",
        quantity=3,
        unit_cost=8,
        line_amount=24,
    )

    assert line_item.quantity == 3.0
    assert line_item.unit_cost == 8.0
    assert line_item.line_amount == 24.0
