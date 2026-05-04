from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class PostingLineItem(BaseModel):
    item_number: str
    description: str
    quantity: float
    unit_cost: float
    line_amount: float


class PurchaseReceiptPosting(BaseModel):
    vendor_number: str
    purchase_order_number: str
    posting_date: date
    document_number: str | None = None
    line_items: list[PostingLineItem]
    total_amount: float


class PostingResult(BaseModel):
    success: bool
    receipt_number: str | None = None
    posted_lines: int = 0
    errors: list[str] = Field(default_factory=list)
    bc_document_url: str | None = None
