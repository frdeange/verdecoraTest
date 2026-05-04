from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import DocumentAnalysisFeature
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential

from .evaluate import SUPPLIER_EXPECTATIONS, evaluate_benchmark_results, page_expectation

DEFAULT_ENDPOINT = "https://verdecora-docintell-dev.cognitiveservices.azure.com/"
DEFAULT_MODELS = ("prebuilt-layout", "prebuilt-invoice")
MODEL_FEATURES: dict[str, list[DocumentAnalysisFeature]] = {
    "prebuilt-layout": [DocumentAnalysisFeature.KEY_VALUE_PAIRS],
    "prebuilt-invoice": [],
}


@dataclass(frozen=True, slots=True)
class ModelRunSummary:
    model_id: str
    average_latency_ms: float
    average_completeness: float
    average_table_count: float
    average_key_value_pair_count: float
    average_document_count: float
    detected_fields: int
    expected_fields: int


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_pdf_path() -> Path:
    return _repo_root() / "prerequisites" / "PRUEBA.pdf"


def _build_client(endpoint: str) -> DocumentIntelligenceClient:
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    return DocumentIntelligenceClient(endpoint=endpoint, credential=credential)


def _cell_pages(cell: Any) -> set[int]:
    pages: set[int] = set()
    for region in getattr(cell, "bounding_regions", []) or []:
        page_number = getattr(region, "page_number", None)
        if isinstance(page_number, int):
            pages.add(page_number)
    return pages


def _table_pages(table: Any) -> set[int]:
    pages: set[int] = set()
    for region in getattr(table, "bounding_regions", []) or []:
        page_number = getattr(region, "page_number", None)
        if isinstance(page_number, int):
            pages.add(page_number)
    return pages


def _table_to_rows(table: Any) -> list[list[str]]:
    rows = [["" for _ in range(int(table.column_count))] for _ in range(int(table.row_count))]
    for cell in table.cells:
        row_index = int(cell.row_index)
        column_index = int(cell.column_index)
        if row_index < len(rows) and column_index < len(rows[row_index]):
            rows[row_index][column_index] = str(cell.content or "")
    return rows


def _tables_for_page(result: Any, page_number: int) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for index, table in enumerate(getattr(result, "tables", []) or []):
        if page_number not in _table_pages(table):
            continue
        tables.append(
            {
                "table_index": index,
                "row_count": int(table.row_count),
                "column_count": int(table.column_count),
                "rows": _table_to_rows(table),
            }
        )
    return tables


def _key_value_pairs_for_page(result: Any, page_number: int) -> list[dict[str, str | None]]:
    pairs: list[dict[str, str | None]] = []
    for pair in getattr(result, "key_value_pairs", []) or []:
        key = getattr(pair, "key", None)
        value = getattr(pair, "value", None)
        pages = set()
        if key is not None:
            pages.update(_cell_pages(key))
        if value is not None:
            pages.update(_cell_pages(value))
        if page_number not in pages:
            continue
        pairs.append(
            {
                "key": getattr(key, "content", None),
                "value": getattr(value, "content", None),
            }
        )
    return pairs


def _serialize_field_value(field: Any) -> Any:
    value = getattr(field, "value", None)
    if isinstance(value, list):
        return [_serialize_field_value(item) for item in value]
    if hasattr(value, "items"):
        return {name: _serialize_field_value(item) for name, item in value.items()}
    return value


def _documents_for_result(result: Any) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for index, document in enumerate(getattr(result, "documents", []) or []):
        fields: dict[str, dict[str, Any]] = {}
        for name, field in (getattr(document, "fields", None) or {}).items():
            fields[name] = {
                "field_type": getattr(field, "type", None),
                "content": getattr(field, "content", None),
                "value": _serialize_field_value(field),
                "confidence": getattr(field, "confidence", None),
            }
        documents.append(
            {
                "document_index": index,
                "doc_type": getattr(document, "doc_type", None),
                "confidence": getattr(document, "confidence", None),
                "fields": fields,
            }
        )
    return documents


def _page_text(page: Any) -> str:
    return "\n".join(line.content for line in getattr(page, "lines", []) or [] if getattr(line, "content", None))


def analyze_page(
    client: DocumentIntelligenceClient,
    pdf_bytes: bytes,
    *,
    page_number: int,
    model_id: str,
) -> dict[str, Any]:
    expectation = page_expectation(page_number)
    start = time.perf_counter()
    poller = client.begin_analyze_document(
        model_id=model_id,
        body=pdf_bytes,
        pages=str(page_number),
        features=MODEL_FEATURES.get(model_id, []),
        output_content_format="text",
    )
    result = poller.result()
    latency_ms = (time.perf_counter() - start) * 1000

    page = next(page for page in result.pages if int(page.page_number) == page_number)
    return {
        "supplier_id": expectation.supplier_id,
        "supplier_name": expectation.supplier_name,
        "page_number": page_number,
        "model_id": model_id,
        "latency_ms": round(latency_ms, 2),
        "table_count": len(_tables_for_page(result, page_number)),
        "key_value_pair_count": len(_key_value_pairs_for_page(result, page_number)),
        "document_count": len(getattr(result, "documents", []) or []),
        "text": _page_text(page),
        "tables": _tables_for_page(result, page_number),
        "key_value_pairs": _key_value_pairs_for_page(result, page_number),
        "documents": _documents_for_result(result),
    }


def _iter_pages() -> Iterable[int]:
    for expectation in SUPPLIER_EXPECTATIONS:
        for page_number in expectation.page_numbers:
            yield page_number


def run_benchmark(pdf_path: Path, endpoint: str, models: tuple[str, ...]) -> dict[str, Any]:
    client = _build_client(endpoint)
    pdf_bytes = pdf_path.read_bytes()
    page_results: list[dict[str, Any]] = []

    for model_id in models:
        print(f"[benchmark] Running {model_id} across {pdf_path.name}")
        for page_number in _iter_pages():
            expectation = page_expectation(page_number)
            print(f"  - page {page_number:02d} · {expectation.supplier_name}")
            try:
                page_results.append(analyze_page(client, pdf_bytes, page_number=page_number, model_id=model_id))
            except HttpResponseError as exc:
                page_results.append(
                    {
                        "supplier_id": expectation.supplier_id,
                        "supplier_name": expectation.supplier_name,
                        "page_number": page_number,
                        "model_id": model_id,
                        "latency_ms": 0.0,
                        "table_count": 0,
                        "key_value_pair_count": 0,
                        "document_count": 0,
                        "text": "",
                        "tables": [],
                        "key_value_pairs": [],
                        "documents": [],
                        "error": str(exc),
                    }
                )

    benchmark_results = {
        "endpoint": endpoint,
        "pdf_path": str(pdf_path),
        "models": list(models),
        "page_results": page_results,
    }
    benchmark_results["evaluation"] = evaluate_benchmark_results(benchmark_results)
    benchmark_results["summary"] = summarize_results(benchmark_results)
    return benchmark_results


def summarize_results(benchmark_results: dict[str, Any]) -> dict[str, Any]:
    evaluation = benchmark_results["evaluation"]
    latency_by_model: dict[str, list[float]] = defaultdict(list)
    tables_by_model: dict[str, list[int]] = defaultdict(list)
    key_values_by_model: dict[str, list[int]] = defaultdict(list)
    documents_by_model: dict[str, list[int]] = defaultdict(list)
    for page_result in benchmark_results["page_results"]:
        model_id = str(page_result["model_id"])
        latency_by_model[model_id].append(float(page_result["latency_ms"]))
        tables_by_model[model_id].append(int(page_result["table_count"]))
        key_values_by_model[model_id].append(int(page_result["key_value_pair_count"]))
        documents_by_model[model_id].append(int(page_result["document_count"]))

    model_summaries: list[dict[str, Any]] = []
    for model_id, model_metrics in evaluation["models"].items():
        summary = ModelRunSummary(
            model_id=model_id,
            average_latency_ms=(sum(latency_by_model[model_id]) / len(latency_by_model[model_id]))
            if latency_by_model[model_id]
            else 0.0,
            average_completeness=float(model_metrics["average_completeness"]),
            average_table_count=(sum(tables_by_model[model_id]) / len(tables_by_model[model_id]))
            if tables_by_model[model_id]
            else 0.0,
            average_key_value_pair_count=(sum(key_values_by_model[model_id]) / len(key_values_by_model[model_id]))
            if key_values_by_model[model_id]
            else 0.0,
            average_document_count=(sum(documents_by_model[model_id]) / len(documents_by_model[model_id]))
            if documents_by_model[model_id]
            else 0.0,
            detected_fields=int(model_metrics["detected_fields"]),
            expected_fields=int(model_metrics["expected_fields"]),
        )
        model_summaries.append(asdict(summary))

    supplier_summaries: dict[str, dict[str, Any]] = {}
    for page_evaluation in evaluation["page_evaluations"]:
        supplier_key = f"{page_evaluation['model_id']}::{page_evaluation['supplier_id']}"
        bucket = supplier_summaries.setdefault(
            supplier_key,
            {
                "model_id": page_evaluation["model_id"],
                "supplier_id": page_evaluation["supplier_id"],
                "supplier_name": page_evaluation["supplier_name"],
                "pages": [],
                "average_completeness": 0.0,
            },
        )
        bucket["pages"].append(page_evaluation["page_number"])
        bucket["average_completeness"] += float(page_evaluation["completeness"])

    for bucket in supplier_summaries.values():
        page_count = len(bucket["pages"])
        bucket["average_completeness"] = bucket["average_completeness"] / page_count if page_count else 0.0

    best_completeness = max(item["average_completeness"] for item in model_summaries)
    close_candidates = [
        item for item in model_summaries if abs(item["average_completeness"] - best_completeness) <= 0.02
    ]

    recommended_model = max(
        close_candidates,
        key=lambda item: (
            item["average_key_value_pair_count"],
            item["average_table_count"],
            item["average_document_count"],
            -item["average_latency_ms"],
        ),
    )["model_id"]
    recommendation_reason = (
        "Field-level accuracy is effectively tied, so prefer prebuilt-layout for heterogeneous supplier packs because "
        "it preserves tables plus key-value pairs on every format."
        if recommended_model == "prebuilt-layout"
        else "prebuilt-invoice wins on the current benchmark mix because it keeps field accuracy while returning the best runtime."
    )

    return {
        "models": model_summaries,
        "suppliers": list(supplier_summaries.values()),
        "recommended_model": recommended_model,
        "recommendation_reason": recommendation_reason,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Document Intelligence OCR extraction on PRUEBA.pdf")
    parser.add_argument("--pdf", type=Path, default=_default_pdf_path(), help="Path to the sample PDF.")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Document Intelligence endpoint.")
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(DEFAULT_MODELS),
        choices=list(DEFAULT_MODELS),
        help="Models to benchmark.",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path.")
    args = parser.parse_args()

    benchmark_results = run_benchmark(args.pdf.resolve(), args.endpoint, tuple(args.models))
    serialized = json.dumps(benchmark_results, ensure_ascii=False, indent=2)

    if args.output is not None:
        args.output.write_text(serialized + "\n", encoding="utf-8")

    print(serialized)


if __name__ == "__main__":
    main()
