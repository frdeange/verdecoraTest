from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

EXPECTED_FIELD_NAMES = (
    "supplier_name",
    "document_date",
    "document_number",
    "line_item_code",
    "line_item_description",
    "line_item_quantity",
    "line_item_price",
)

DATE_PATTERN = re.compile(
    r"\b(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}[./-]\d{1,2}[./-]\d{1,2}|\d{1,2}\s+[A-Za-z]{3,12}\s+\d{2,4})\b"
)
NUMBER_LABEL_PATTERN = re.compile(
    r"\b(?:albara?n|albara?n no|invoice|fattura|factura|ddt|document(?:o)?|liefer(?:schein)?|nota)\b",
    re.IGNORECASE,
)

CODE_HINTS = ("ean", "barcode", "item", "art", "articolo", "codigo", "codice", "ref", "sku", "sscc")
DESCRIPTION_HINTS = ("description", "descripcion", "descrizione", "artikel", "articulo", "item", "producto")
QUANTITY_HINTS = ("qty", "quantity", "quantita", "cantidad", "uds", "ud", "boxes", "pallet", "palet", "colli")
PRICE_HINTS = ("price", "precio", "importe", "amount", "pvp", "unit", "cost", "eur", "neto", "totale")


@dataclass(frozen=True, slots=True)
class SupplierExpectation:
    supplier_id: str
    supplier_name: str
    page_numbers: tuple[int, ...]
    aliases: tuple[str, ...]
    expects_document_date: bool = True
    expects_document_number: bool = True
    expects_line_item_code: bool = True
    expects_line_item_description: bool = True
    expects_line_item_quantity: bool = True
    expects_line_item_price: bool = True
    notes: str = ""


@dataclass(frozen=True, slots=True)
class FieldEvaluation:
    detected: bool
    evidence: str | None = None


@dataclass(frozen=True, slots=True)
class PageEvaluation:
    supplier_id: str
    supplier_name: str
    page_number: int
    model_id: str
    fields: dict[str, FieldEvaluation]
    detected_fields: int
    expected_fields: int
    completeness: float

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["fields"] = {name: asdict(field) for name, field in self.fields.items()}
        return data


SUPPLIER_EXPECTATIONS: tuple[SupplierExpectation, ...] = (
    SupplierExpectation(
        supplier_id="herstera",
        supplier_name="Herstera Garden S.L.",
        page_numbers=(1, 2, 3, 4),
        aliases=("Herstera Garden S.L.", "Herstera Garden", "Herstera"),
        notes="Structured table with EAN codes and multi-page continuity.",
    ),
    SupplierExpectation(
        supplier_id="fansa",
        supplier_name="FANSA",
        page_numbers=(5,),
        aliases=("FANSA",),
        notes="Monospaced invoice with handwritten numeric corrections and stamps.",
    ),
    SupplierExpectation(
        supplier_id="royal_canin",
        supplier_name="Royal Canin Ibérica",
        page_numbers=(6,),
        aliases=("Royal Canin Ibérica", "Royal Canin Iberica", "Royal Canin"),
        notes="Pet-food invoice with lots and expiry dates.",
    ),
    SupplierExpectation(
        supplier_id="hobbit_alf",
        supplier_name="HOBBIT-ALF S.L.",
        page_numbers=(7, 8),
        aliases=("HOBBIT-ALF S.L.", "HOBBIT-ALF", "Hobbit-Alf"),
        notes="Italian-style export invoice with IBAN-heavy headers.",
    ),
    SupplierExpectation(
        supplier_id="veca",
        supplier_name="VECA S.p.A",
        page_numbers=(9, 10),
        aliases=("VECA S.p.A", "VECA", "Veca"),
        notes="Dense Italian columns with handwritten annotations.",
    ),
    SupplierExpectation(
        supplier_id="sera",
        supplier_name="sera GmbH",
        page_numbers=(11, 12, 13),
        aliases=("sera GmbH", "sera", "Sera GmbH"),
        notes="German multi-page format with boxes and pallets.",
    ),
    SupplierExpectation(
        supplier_id="trixie",
        supplier_name="triXder/Trixie",
        page_numbers=(14, 15),
        aliases=("triXder", "Trixie", "triXie", "TRIXIE"),
        notes="Factura with PVP columns and mixed casing on supplier brand.",
    ),
    SupplierExpectation(
        supplier_id="saneaplast",
        supplier_name="Saneaplast",
        page_numbers=(16, 19),
        aliases=("Saneaplast",),
        notes="Grid layout with discounts and duplicated albaranes.",
    ),
    SupplierExpectation(
        supplier_id="catral",
        supplier_name="Catral",
        page_numbers=(17, 18),
        aliases=("Catral",),
        expects_line_item_price=False,
        notes="Albarán plus packing list; SSCC barcodes matter more than prices.",
    ),
)

SUPPLIER_BY_PAGE = {
    page_number: expectation for expectation in SUPPLIER_EXPECTATIONS for page_number in expectation.page_numbers
}


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(character for character in normalized if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", without_accents).strip().lower()


def page_expectation(page_number: int) -> SupplierExpectation:
    try:
        return SUPPLIER_BY_PAGE[page_number]
    except KeyError as exc:
        raise ValueError(f"No supplier expectation configured for page {page_number}.") from exc


def _field_content(field_data: Mapping[str, Any]) -> str:
    content = field_data.get("content")
    if isinstance(content, str) and content.strip():
        return content

    value = field_data.get("value")
    if isinstance(value, str) and value.strip():
        return value

    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _document_field_text(page_data: Mapping[str, Any]) -> str:
    documents = page_data.get("documents", [])
    if not isinstance(documents, list):
        return ""

    parts: list[str] = []
    for document in documents:
        if not isinstance(document, Mapping):
            continue
        for name, field_data in document.get("fields", {}).items():
            if not isinstance(field_data, Mapping):
                continue
            parts.append(f"{name}: {_field_content(field_data)}")
    return "\n".join(parts)


def _key_value_text(page_data: Mapping[str, Any]) -> str:
    pairs = page_data.get("key_value_pairs", [])
    if not isinstance(pairs, list):
        return ""

    lines: list[str] = []
    for pair in pairs:
        if not isinstance(pair, Mapping):
            continue
        key = pair.get("key")
        value = pair.get("value")
        if key or value:
            lines.append(f"{key or ''}: {value or ''}")
    return "\n".join(lines)


def _table_rows(page_data: Mapping[str, Any]) -> list[list[str]]:
    tables = page_data.get("tables", [])
    if not isinstance(tables, list):
        return []

    rows: list[list[str]] = []
    for table in tables:
        if not isinstance(table, Mapping):
            continue
        row_data = table.get("rows", [])
        if not isinstance(row_data, list):
            continue
        for row in row_data:
            if isinstance(row, list):
                rows.append([str(cell) for cell in row])
    return rows


def _search_blob(page_data: Mapping[str, Any]) -> str:
    parts = [
        str(page_data.get("text", "")),
        _key_value_text(page_data),
        _document_field_text(page_data),
    ]
    parts.extend(" | ".join(row) for row in _table_rows(page_data))
    return "\n".join(part for part in parts if part)


def _find_alias(blob: str, aliases: Iterable[str]) -> str | None:
    normalized_blob = normalize_text(blob)
    for alias in aliases:
        if normalize_text(alias) in normalized_blob:
            return alias
    return None


def _detect_supplier_name(page_data: Mapping[str, Any], expectation: SupplierExpectation) -> FieldEvaluation:
    evidence = _find_alias(_search_blob(page_data), expectation.aliases)
    return FieldEvaluation(detected=evidence is not None, evidence=evidence)


def _detect_document_date(page_data: Mapping[str, Any]) -> FieldEvaluation:
    match = DATE_PATTERN.search(_search_blob(page_data))
    return FieldEvaluation(detected=match is not None, evidence=match.group(0) if match else None)


def _detect_document_number(page_data: Mapping[str, Any]) -> FieldEvaluation:
    blob = _search_blob(page_data)
    lines = [line.strip() for line in blob.splitlines() if line.strip()]
    for line in lines:
        if NUMBER_LABEL_PATTERN.search(line):
            compact = re.sub(r"\s+", " ", line)
            return FieldEvaluation(detected=True, evidence=compact[:120])

    token_match = re.search(r"\b[A-Z]{1,6}[-./]?\d{2,}[A-Z0-9./-]*\b", blob)
    return FieldEvaluation(detected=token_match is not None, evidence=token_match.group(0) if token_match else None)


def _header_blob(page_data: Mapping[str, Any]) -> str:
    header_candidates: list[str] = []
    for row in _table_rows(page_data)[:6]:
        header_candidates.append(" | ".join(row))
    return normalize_text("\n".join(header_candidates))


def _contains_any(blob: str, hints: Iterable[str]) -> str | None:
    for hint in hints:
        if normalize_text(hint) in blob:
            return hint
    return None


def _detect_line_item_code(page_data: Mapping[str, Any]) -> FieldEvaluation:
    header_blob = _header_blob(page_data)
    hint = _contains_any(header_blob, CODE_HINTS)
    if hint is not None:
        return FieldEvaluation(detected=True, evidence=hint)

    for row in _table_rows(page_data):
        for cell in row:
            if re.search(r"\b\d{8,14}\b", cell):
                return FieldEvaluation(detected=True, evidence=cell)
    return FieldEvaluation(detected=False)


def _detect_line_item_description(page_data: Mapping[str, Any]) -> FieldEvaluation:
    header_blob = _header_blob(page_data)
    hint = _contains_any(header_blob, DESCRIPTION_HINTS)
    if hint is not None:
        return FieldEvaluation(detected=True, evidence=hint)

    for row in _table_rows(page_data):
        for cell in row:
            words = [part for part in re.split(r"\s+", cell.strip()) if part]
            if len(words) >= 3 and not re.fullmatch(r"[\d.,-]+", cell.strip()):
                return FieldEvaluation(detected=True, evidence=cell[:120])
    return FieldEvaluation(detected=False)


def _detect_line_item_quantity(page_data: Mapping[str, Any]) -> FieldEvaluation:
    header_blob = _header_blob(page_data)
    hint = _contains_any(header_blob, QUANTITY_HINTS)
    if hint is not None:
        return FieldEvaluation(detected=True, evidence=hint)

    for row in _table_rows(page_data):
        numeric_cells = [cell for cell in row if re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", cell.strip())]
        if numeric_cells:
            return FieldEvaluation(detected=True, evidence=numeric_cells[0])
    return FieldEvaluation(detected=False)


def _detect_line_item_price(page_data: Mapping[str, Any]) -> FieldEvaluation:
    header_blob = _header_blob(page_data)
    hint = _contains_any(header_blob, PRICE_HINTS)
    if hint is not None:
        return FieldEvaluation(detected=True, evidence=hint)

    for row in _table_rows(page_data):
        for cell in row:
            if re.fullmatch(r"[-+]?\d+[.,]\d{2,4}", cell.strip()):
                return FieldEvaluation(detected=True, evidence=cell)
    return FieldEvaluation(detected=False)


def evaluate_page_extraction(
    page_data: Mapping[str, Any], expectation: SupplierExpectation | None = None
) -> PageEvaluation:
    page_number = int(page_data["page_number"])
    resolved_expectation = expectation or page_expectation(page_number)

    detected_fields = {
        "supplier_name": _detect_supplier_name(page_data, resolved_expectation),
        "document_date": _detect_document_date(page_data),
        "document_number": _detect_document_number(page_data),
        "line_item_code": _detect_line_item_code(page_data),
        "line_item_description": _detect_line_item_description(page_data),
        "line_item_quantity": _detect_line_item_quantity(page_data),
        "line_item_price": _detect_line_item_price(page_data),
    }

    expected_flags = {
        "supplier_name": True,
        "document_date": resolved_expectation.expects_document_date,
        "document_number": resolved_expectation.expects_document_number,
        "line_item_code": resolved_expectation.expects_line_item_code,
        "line_item_description": resolved_expectation.expects_line_item_description,
        "line_item_quantity": resolved_expectation.expects_line_item_quantity,
        "line_item_price": resolved_expectation.expects_line_item_price,
    }

    filtered_fields = {name: detected_fields[name] for name in EXPECTED_FIELD_NAMES if expected_flags[name]}
    detected_count = sum(1 for field in filtered_fields.values() if field.detected)
    expected_count = len(filtered_fields)
    completeness = detected_count / expected_count if expected_count else 1.0

    return PageEvaluation(
        supplier_id=resolved_expectation.supplier_id,
        supplier_name=resolved_expectation.supplier_name,
        page_number=page_number,
        model_id=str(page_data["model_id"]),
        fields=filtered_fields,
        detected_fields=detected_count,
        expected_fields=expected_count,
        completeness=completeness,
    )


def evaluate_benchmark_results(benchmark_results: Mapping[str, Any]) -> dict[str, Any]:
    page_results = benchmark_results.get("page_results", [])
    if not isinstance(page_results, list):
        raise ValueError("Benchmark results must contain a 'page_results' list.")

    evaluations = [
        evaluate_page_extraction(page_result).to_dict()
        for page_result in page_results
        if isinstance(page_result, Mapping)
    ]
    by_model: dict[str, dict[str, Any]] = {}
    for evaluation in evaluations:
        model_id = str(evaluation["model_id"])
        model_bucket = by_model.setdefault(
            model_id,
            {
                "pages": 0,
                "detected_fields": 0,
                "expected_fields": 0,
                "average_completeness": 0.0,
                "field_detection_rate": {},
            },
        )
        model_bucket["pages"] += 1
        model_bucket["detected_fields"] += int(evaluation["detected_fields"])
        model_bucket["expected_fields"] += int(evaluation["expected_fields"])

        for field_name, field_result in evaluation["fields"].items():
            field_bucket = model_bucket["field_detection_rate"].setdefault(field_name, {"detected": 0, "expected": 0})
            field_bucket["expected"] += 1
            if field_result["detected"]:
                field_bucket["detected"] += 1

    for model_bucket in by_model.values():
        model_bucket["average_completeness"] = (
            model_bucket["detected_fields"] / model_bucket["expected_fields"]
            if model_bucket["expected_fields"]
            else 1.0
        )
        for field_bucket in model_bucket["field_detection_rate"].values():
            field_bucket["accuracy"] = (
                field_bucket["detected"] / field_bucket["expected"] if field_bucket["expected"] else 1.0
            )

    return {
        "expectations": [asdict(expectation) for expectation in SUPPLIER_EXPECTATIONS],
        "page_evaluations": evaluations,
        "models": by_model,
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate OCR benchmark output against supplier expectations.")
    parser.add_argument("--input", type=Path, required=True, help="Path to the benchmark JSON output.")
    parser.add_argument("--output", type=Path, help="Optional path to write the evaluation JSON.")
    args = parser.parse_args()

    evaluation = evaluate_benchmark_results(_read_json(args.input))
    serialized = json.dumps(evaluation, ensure_ascii=False, indent=2)

    if args.output is not None:
        args.output.write_text(serialized + "\n", encoding="utf-8")

    print(serialized)


if __name__ == "__main__":
    main()
