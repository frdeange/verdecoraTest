from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TableCell(BaseModel):
    """A single extracted table cell."""

    model_config = ConfigDict(extra="forbid")

    row_index: int
    column_index: int
    content: str
    kind: str | None = None
    page_number: int | None = None


class Table(BaseModel):
    """A normalized representation of a Document Intelligence table."""

    model_config = ConfigDict(extra="forbid")

    row_count: int
    column_count: int
    cells: list[TableCell] = Field(default_factory=list)


class KVPair(BaseModel):
    """A normalized key-value pair extracted from a document."""

    model_config = ConfigDict(extra="forbid")

    key: str
    value: str | None = None
    confidence: float | None = None


class AnalysisResult(BaseModel):
    """A simplified document analysis result."""

    model_config = ConfigDict(extra="forbid")

    model_id: str
    content: str
    page_count: int
    tables: list[Table] = Field(default_factory=list)
    key_value_pairs: list[KVPair] = Field(default_factory=list)


class InvoiceField(BaseModel):
    """A normalized invoice field value."""

    model_config = ConfigDict(extra="forbid")

    name: str
    value: Any = None
    content: str | None = None
    confidence: float | None = None


class InvoiceResult(BaseModel):
    """A simplified invoice analysis payload."""

    model_config = ConfigDict(extra="forbid")

    vendor_name: str | None = None
    customer_name: str | None = None
    invoice_id: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    total_amount: float | None = None
    currency: str | None = None
    fields: list[InvoiceField] = Field(default_factory=list)
    line_items: list[dict[str, Any]] = Field(default_factory=list)
