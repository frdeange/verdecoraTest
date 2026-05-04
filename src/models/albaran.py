from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    ALBARAN = "albaran"
    FACTURA = "factura"
    PACKING_LIST = "packing_list"
    UNKNOWN = "unknown"


class LineItem(BaseModel):
    line_number: int
    product_code: str | None = None
    ean_code: str | None = None
    description: str
    quantity: float
    unit_price: float | None = None
    discount_pct: float | None = None
    total: float | None = None
    lot_number: str | None = None
    expiry_date: date | None = None


class AlbaranHeader(BaseModel):
    supplier_name: str
    supplier_tax_id: str | None = None
    document_type: DocumentType
    document_number: str
    document_date: date | None = None
    delivery_date: date | None = None
    purchase_order_number: str | None = None
    store_name: str | None = None
    total_amount: float | None = None
    currency: str = "EUR"


class AlbaranExtraction(BaseModel):
    header: AlbaranHeader
    line_items: list[LineItem]
    raw_text: str | None = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    extraction_warnings: list[str] = Field(default_factory=list)
    source_pages: list[int] = Field(default_factory=list)


class TriageResult(BaseModel):
    document_type: DocumentType
    language: str = "es"
    supplier_id: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    routing_decision: str
    reasoning: str


class CoherenceCheckResult(BaseModel):
    is_coherent: bool
    overall_confidence: float = Field(ge=0.0, le=1.0)
    header_issues: list[str] = Field(default_factory=list)
    line_item_issues: list[str] = Field(default_factory=list)
    bc_match_found: bool = False
    matched_po_number: str | None = None
    suggested_corrections: dict[str, str] = Field(default_factory=dict)
