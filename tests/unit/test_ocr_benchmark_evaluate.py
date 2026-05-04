from __future__ import annotations

from src.poc.ocr_benchmark.evaluate import evaluate_benchmark_results, evaluate_page_extraction, page_expectation


def test_evaluate_page_extraction_detects_expected_fields() -> None:
    page_result = {
        "supplier_id": "herstera",
        "supplier_name": "Herstera Garden S.L.",
        "page_number": 1,
        "model_id": "prebuilt-layout",
        "text": "Herstera Garden S.L.\nAlbarán HG-2024-0001\nFecha 01/02/2024",
        "tables": [
            {
                "rows": [
                    ["EAN", "Descripción", "Cantidad", "Precio"],
                    ["8437000000012", "Jardinera verde", "10", "12,50"],
                ]
            }
        ],
        "key_value_pairs": [{"key": "Fecha", "value": "01/02/2024"}],
        "documents": [],
    }

    evaluation = evaluate_page_extraction(page_result, page_expectation(1))

    assert evaluation.detected_fields == evaluation.expected_fields
    assert evaluation.completeness == 1.0
    assert evaluation.fields["supplier_name"].detected is True
    assert evaluation.fields["document_number"].detected is True
    assert evaluation.fields["line_item_price"].detected is True


def test_evaluate_benchmark_results_aggregates_models() -> None:
    benchmark_results = {
        "page_results": [
            {
                "supplier_id": "catral",
                "supplier_name": "Catral",
                "page_number": 17,
                "model_id": "prebuilt-layout",
                "text": "Catral\nPacking list\n17/04/2024",
                "tables": [{"rows": [["SSCC", "Descripción", "Cantidad"], ["12345678901234", "Malla", "4"]]}],
                "key_value_pairs": [],
                "documents": [],
            },
            {
                "supplier_id": "catral",
                "supplier_name": "Catral",
                "page_number": 17,
                "model_id": "prebuilt-invoice",
                "text": "Catral\nPacking list",
                "tables": [{"rows": [["Descripción", "Cantidad"], ["Malla", "4"]]}],
                "key_value_pairs": [],
                "documents": [],
            },
        ]
    }

    evaluation = evaluate_benchmark_results(benchmark_results)

    assert set(evaluation["models"]) == {"prebuilt-layout", "prebuilt-invoice"}
    assert evaluation["models"]["prebuilt-layout"]["field_detection_rate"]["supplier_name"]["accuracy"] == 1.0
    assert (
        evaluation["models"]["prebuilt-layout"]["average_completeness"]
        >= evaluation["models"]["prebuilt-invoice"]["average_completeness"]
    )
