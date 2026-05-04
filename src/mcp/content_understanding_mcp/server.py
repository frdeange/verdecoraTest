from __future__ import annotations

import base64
import binascii
from functools import lru_cache
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    AnalyzeDocumentRequest,
    AnalyzeResult,
    DocumentAnalysisFeature,
    DocumentField,
)
from azure.core.exceptions import HttpResponseError
from mcp.server.fastmcp import FastMCP

from src.mcp.common import MCPServerError, MCPValidationError, get_default_credential, is_http_url, require_env
from src.mcp.content_understanding_mcp.models import AnalysisResult as MCPAnalysisResult
from src.mcp.content_understanding_mcp.models import InvoiceField, InvoiceResult, KVPair, Table, TableCell

mcp = FastMCP("verdecora-content-understanding-mcp", json_response=True)


class ContentUnderstandingMCPError(MCPServerError):
    """Base error for Document Intelligence MCP failures."""


class ContentUnderstandingOperationError(ContentUnderstandingMCPError):
    """Raised when the Document Intelligence service call fails."""


@lru_cache(maxsize=1)
def get_document_intelligence_client() -> DocumentIntelligenceClient:
    """Create a cached Document Intelligence client authenticated with managed identity."""

    return DocumentIntelligenceClient(endpoint=require_env("DOCINTELL_ENDPOINT"), credential=get_default_credential())


def build_analyze_request(document_url_or_base64: str) -> AnalyzeDocumentRequest:
    """Create an AnalyzeDocumentRequest from a URL or a base64-encoded payload."""

    candidate = document_url_or_base64.strip()
    if not candidate:
        raise MCPValidationError("document_url_or_base64 must not be empty")

    if is_http_url(candidate):
        return AnalyzeDocumentRequest(url_source=candidate)

    try:
        document_bytes = base64.b64decode(candidate, validate=True)
    except binascii.Error as exc:
        raise MCPValidationError("document_url_or_base64 must be a valid HTTP(S) URL or base64 string") from exc

    return AnalyzeDocumentRequest(bytes_source=document_bytes)


def run_analysis(document_url_or_base64: str, model_id: str, *, include_key_value_pairs: bool = True) -> AnalyzeResult:
    """Execute a document analysis request and return the raw Azure SDK result."""

    features: list[str | DocumentAnalysisFeature] | None = (
        [DocumentAnalysisFeature.KEY_VALUE_PAIRS] if include_key_value_pairs else None
    )

    try:
        poller = get_document_intelligence_client().begin_analyze_document(
            model_id=model_id,
            body=build_analyze_request(document_url_or_base64),
            features=features,
        )
        return poller.result()
    except HttpResponseError as exc:
        raise ContentUnderstandingOperationError(
            f"Document analysis failed for model '{model_id}': {exc.message}"
        ) from exc


def to_tables(result: AnalyzeResult) -> list[Table]:
    """Convert SDK table objects into MCP-friendly models."""

    tables: list[Table] = []
    for table in result.tables or []:
        cells = [
            TableCell(
                row_index=cell.row_index,
                column_index=cell.column_index,
                content=cell.content,
                kind=cell.kind,
                page_number=cell.bounding_regions[0].page_number if cell.bounding_regions else None,
            )
            for cell in table.cells
        ]
        tables.append(Table(row_count=table.row_count, column_count=table.column_count, cells=cells))
    return tables


def to_key_value_pairs(result: AnalyzeResult) -> list[KVPair]:
    """Convert SDK key-value pairs into MCP-friendly models."""

    pairs: list[KVPair] = []
    for pair in result.key_value_pairs or []:
        key_content = pair.key.content if pair.key else ""
        value_content = pair.value.content if pair.value else None
        pairs.append(KVPair(key=key_content, value=value_content, confidence=pair.confidence))
    return pairs


def document_field_value(field: DocumentField) -> Any:
    """Return the best available scalar or composite value for an invoice field."""

    for attribute_name in (
        "value_string",
        "value_currency",
        "value_number",
        "value_date",
        "value_integer",
        "value_phone_number",
        "value_country_region",
        "value_selection_mark",
    ):
        value = getattr(field, attribute_name, None)
        if value is not None:
            if hasattr(value, "amount"):
                return value.amount
            if hasattr(value, "currency_code"):
                return value.currency_code
            return value

    if field.value_object:
        return {key: document_field_value(nested_field) for key, nested_field in field.value_object.items()}
    if field.value_array:
        return [document_field_value(nested_field) for nested_field in field.value_array]
    return field.content


def extract_invoice_result(result: AnalyzeResult) -> InvoiceResult:
    """Build a normalized invoice payload from the raw SDK result."""

    document = result.documents[0] if result.documents else None
    fields: dict[str, DocumentField] = (document.fields or {}) if document else {}

    normalized_fields = [
        InvoiceField(
            name=name,
            value=document_field_value(field),
            content=field.content,
            confidence=field.confidence,
        )
        for name, field in fields.items()
    ]

    line_items_field = fields.get("Items")
    line_items = []
    if line_items_field and line_items_field.value_array:
        for item in line_items_field.value_array:
            if item.value_object:
                line_items.append({key: document_field_value(value) for key, value in item.value_object.items()})

    total_field = fields.get("InvoiceTotal")
    vendor_name_field = fields.get("VendorName")
    customer_name_field = fields.get("CustomerName")
    invoice_id_field = fields.get("InvoiceId")
    invoice_date_field = fields.get("InvoiceDate")
    due_date_field = fields.get("DueDate")

    total_amount = None
    currency = None
    if total_field and total_field.value_currency:
        total_amount = total_field.value_currency.amount
        currency = total_field.value_currency.currency_code

    invoice_date = str(invoice_date_field.value_date) if invoice_date_field and invoice_date_field.value_date else None
    due_date = str(due_date_field.value_date) if due_date_field and due_date_field.value_date else None

    return InvoiceResult(
        vendor_name=vendor_name_field.content if vendor_name_field else None,
        customer_name=customer_name_field.content if customer_name_field else None,
        invoice_id=invoice_id_field.content if invoice_id_field else None,
        invoice_date=invoice_date,
        due_date=due_date,
        total_amount=total_amount,
        currency=currency,
        fields=normalized_fields,
        line_items=line_items,
    )


@mcp.tool()
def analyze_document(document_url_or_base64: str, model_id: str = "prebuilt-layout") -> dict[str, Any]:
    """Analyze a document with Azure AI Document Intelligence."""

    result = run_analysis(document_url_or_base64, model_id)
    normalized = MCPAnalysisResult(
        model_id=model_id,
        content=result.content,
        page_count=len(result.pages or []),
        tables=to_tables(result),
        key_value_pairs=to_key_value_pairs(result),
    )
    return normalized.model_dump()


@mcp.tool()
def analyze_invoice(document_url_or_base64: str) -> dict[str, Any]:
    """Analyze an invoice document and return normalized invoice fields."""

    result = run_analysis(document_url_or_base64, "prebuilt-invoice")
    return extract_invoice_result(result).model_dump()


@mcp.tool()
def extract_tables(document_url_or_base64: str) -> list[dict[str, Any]]:
    """Extract tables from a document using the prebuilt layout model."""

    result = run_analysis(document_url_or_base64, "prebuilt-layout", include_key_value_pairs=False)
    return [table.model_dump() for table in to_tables(result)]


@mcp.tool()
def extract_key_value_pairs(document_url_or_base64: str) -> list[dict[str, Any]]:
    """Extract key-value pairs from a document."""

    result = run_analysis(document_url_or_base64, "prebuilt-document")
    return [pair.model_dump() for pair in to_key_value_pairs(result)]


def main() -> None:
    """Run the Document Intelligence MCP server."""

    mcp.run()


if __name__ == "__main__":
    main()
