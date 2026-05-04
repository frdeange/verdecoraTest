# OCR extraction benchmark — Azure AI Document Intelligence

## Decision

**Recommendation:** use **Azure AI Document Intelligence `prebuilt-layout`** as the extraction engine for Verdecora supplier delivery notes and invoices.

`prebuilt-invoice` was faster, but `prebuilt-layout` handled the mixed supplier pack more safely because it preserved tables and key-value pairs across all nine formats without assuming a pure invoice schema.

## Scope

- Sample: `prerequisites/PRUEBA.pdf`
- Pages: 19
- Supplier formats covered: 9
- Models benchmarked:
  - `prebuilt-layout`
  - `prebuilt-invoice`
- Authentication: `DefaultAzureCredential` via Azure CLI sign-in (`admin@gpsazure.com`)
- Resource: `verdecora-docintell-dev` (`swedencentral`)

## Methodology

The benchmark script (`python -m src.poc.ocr_benchmark.benchmark`) analyzes the PDF **page by page** with both models.

For each page it captures:

- full OCR text
- detected tables
- key-value pairs
- typed document fields (when available)
- latency per page

The evaluation module (`python -m src.poc.ocr_benchmark.evaluate --input <json>`) compares the extracted output against manual expectations per supplier format:

- supplier name
- document date
- albarán / invoice number
- line-item code
- line-item description
- line-item quantity
- line-item price

Field-level completeness is calculated as detected expected fields ÷ expected fields.

## Overall results

| Model | Avg latency / page | Field completeness | Avg tables / page | Avg KV pairs / page | Avg typed docs / page |
|---|---:|---:|---:|---:|---:|
| `prebuilt-layout` | 11.82 s | 96.95% (127/131) | 3.11 | 26.68 | 0.00 |
| `prebuilt-invoice` | 7.48 s | 96.95% (127/131) | 3.11 | 0.00 | 1.00 |

### Field-level detection

| Field | Accuracy |
|---|---:|
| Supplier name | 100% |
| Date | 100% |
| Document number | 100% |
| Line-item code | 100% |
| Line-item description | 100% |
| Line-item quantity | 100% |
| Line-item price | 76.47% |

The only repeated misses were **line-item price** on the hardest pages.

## Results by supplier format

| Supplier | Pages | Layout completeness | Invoice completeness | Notes |
|---|---:|---:|---:|---|
| Herstera Garden S.L. | 1-4 | 100.00% | 100.00% | Best-case structured multi-page table with EAN columns. |
| FANSA | 5 | 85.71% | 85.71% | Handwritten numbers / stamps; price extraction was the weak spot. |
| Royal Canin Ibérica | 6 | 100.00% | 100.00% | Clean extraction despite lots / expiry content. |
| HOBBIT-ALF S.L. | 7-8 | 100.00% | 100.00% | Italian export layout still mapped reliably. |
| VECA S.p.A | 9-10 | 92.86% | 92.86% | Dense columns and annotations degraded price capture on one page. |
| sera GmbH | 11-13 | 90.48% | 90.48% | German multi-page format with pallets / boxes was the hardest multi-page supplier. |
| triXder/Trixie | 14-15 | 100.00% | 100.00% | PVP-heavy invoice structure extracted cleanly. |
| Saneaplast | 16, 19 | 100.00% | 100.00% | Discounts and duplicated albaranes were still recoverable. |
| Catral | 17-18 | 100.00% | 100.00% | Packing-list style worked well; price not required for this format. |

## Key findings

1. **Document Intelligence is viable for all 9 supplier formats.** Both models extracted the core operational fields on every supplier.
2. **`prebuilt-invoice` is faster** (~7.5 s/page vs ~11.8 s/page).
3. **`prebuilt-layout` is the safer default for Verdecora** because the corpus is not a pure invoice corpus:
   - albaranes
   - export invoices
   - packing lists
   - dense supplier-specific grids
   - pages with handwriting / stamps / barcodes
4. **Price extraction is the main weak area** on:
   - FANSA
   - VECA page 10
   - sera pages 11-12
5. **Post-processing is still required** for production-grade normalization:
   - strip `:selected:` artifacts from OCR tables
   - merge split multi-line cells
   - normalize decimal separators and quantity noise
   - reconcile supplier aliases (`triXder` vs `Trixie`)
   - use supplier-specific parsers for pallets, lots, SSCC, and duplicate albaranes

## Recommended implementation approach

Use `prebuilt-layout` as the base extractor, then add Verdecora post-processing in the ingestion pipeline:

1. run `prebuilt-layout`
2. normalize OCR text, tables, and key-value pairs
3. apply supplier-specific enrichment rules
4. map normalized fields into the Verdecora albarán schema
5. keep `prebuilt-invoice` available only as a fallback / diagnostic comparison path

## Files

- `src/poc/ocr_benchmark/benchmark.py`
- `src/poc/ocr_benchmark/evaluate.py`
- `src/poc/ocr_benchmark/requirements.txt`

## Repro

```bash
pip install -r src/poc/ocr_benchmark/requirements.txt
python -m src.poc.ocr_benchmark.benchmark --output .copilot/ocr-benchmark-results.json
python -m src.poc.ocr_benchmark.evaluate --input .copilot/ocr-benchmark-results.json
```
