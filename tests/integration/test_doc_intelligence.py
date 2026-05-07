"""Integration test: Document Intelligence OCR with PRUEBA.pdf (Issue #155).

Requires:
  - DOCINTELL_ENDPOINT env var (or uses default dev endpoint)
  - Azure CLI login (DefaultAzureCredential)
  - prerequisites/PRUEBA.pdf must exist
"""

import os
import sys
import time

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.identity import DefaultAzureCredential

ENDPOINT = os.getenv(
    "DOCINTELL_ENDPOINT",
    "https://verdecora-docintell-dev.cognitiveservices.azure.com/",
)
PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "prerequisites", "PRUEBA.pdf")


def get_client() -> DocumentIntelligenceClient:
    credential = DefaultAzureCredential()
    return DocumentIntelligenceClient(endpoint=ENDPOINT, credential=credential)


def test_prebuilt_layout():
    """Test prebuilt-layout model (general OCR + tables)."""
    print(f"\n{'='*60}")
    print("Testing prebuilt-layout model")
    print(f"Endpoint: {ENDPOINT}")
    print(f"PDF: {os.path.abspath(PDF_PATH)}")
    print(f"{'='*60}")

    if not os.path.exists(PDF_PATH):
        print(f"❌ PDF not found: {PDF_PATH}")
        return {"model": "prebuilt-layout", "status": "SKIP", "error": "PDF not found"}

    client = get_client()

    with open(PDF_PATH, "rb") as f:
        pdf_bytes = f.read()

    print(f"   PDF size: {len(pdf_bytes):,} bytes")

    t0 = time.time()
    poller = client.begin_analyze_document(
        model_id="prebuilt-layout",
        body=pdf_bytes,
        content_type="application/pdf",
    )
    result = poller.result()
    elapsed = time.time() - t0

    pages = result.pages or []
    tables = result.tables or []
    paragraphs = result.paragraphs or []

    print(f"✅ Analysis complete in {elapsed:.1f}s")
    print(f"   Pages: {len(pages)}")
    print(f"   Tables: {len(tables)}")
    print(f"   Paragraphs: {len(paragraphs)}")

    if pages:
        p = pages[0]
        print(f"   Page 1: {p.width}x{p.height} {p.unit}, {len(p.words or [])} words")

    if tables:
        t = tables[0]
        print(f"   Table 1: {t.row_count}x{t.column_count}")

    # Show first 500 chars of extracted text
    full_text = "\n".join(p.content for p in paragraphs if p.content) if paragraphs else ""
    if full_text:
        print(f"   Text preview: {full_text[:500]}...")

    return {
        "model": "prebuilt-layout",
        "status": "OK",
        "pages": len(pages),
        "tables": len(tables),
        "paragraphs": len(paragraphs),
        "elapsed_s": round(elapsed, 1),
    }


def test_prebuilt_invoice():
    """Test prebuilt-invoice model (invoice-specific extraction)."""
    print(f"\n{'='*60}")
    print("Testing prebuilt-invoice model")
    print(f"{'='*60}")

    if not os.path.exists(PDF_PATH):
        print(f"❌ PDF not found: {PDF_PATH}")
        return {"model": "prebuilt-invoice", "status": "SKIP", "error": "PDF not found"}

    client = get_client()

    with open(PDF_PATH, "rb") as f:
        pdf_bytes = f.read()

    t0 = time.time()
    poller = client.begin_analyze_document(
        model_id="prebuilt-invoice",
        body=pdf_bytes,
        content_type="application/pdf",
    )
    result = poller.result()
    elapsed = time.time() - t0

    documents = result.documents or []
    print(f"✅ Invoice analysis complete in {elapsed:.1f}s")
    print(f"   Documents extracted: {len(documents)}")

    for i, doc in enumerate(documents):
        print(f"\n   Document {i+1} (type: {doc.doc_type}):")
        fields = doc.fields or {}
        for key in ["VendorName", "InvoiceTotal", "InvoiceDate", "InvoiceId", "CustomerName"]:
            if key in fields:
                f = fields[key]
                print(f"     {key}: {f.content} (confidence: {f.confidence:.2f})")

    return {
        "model": "prebuilt-invoice",
        "status": "OK",
        "documents": len(documents),
        "elapsed_s": round(elapsed, 1),
    }


def main():
    print("🚀 Document Intelligence Integration Test")
    print(f"Endpoint: {ENDPOINT}")
    results = []

    results.append(test_prebuilt_layout())
    results.append(test_prebuilt_invoice())

    print(f"\n{'='*60}")
    print("📊 Summary")
    print(f"{'='*60}")
    errors = [r for r in results if r["status"] not in ("OK", "SKIP")]
    for r in results:
        icon = {"OK": "✅", "SKIP": "⏭️"}.get(r["status"], "❌")
        print(f"  {icon} {r['model']}: {r['status']}")

    if errors:
        print(f"\n❌ {len(errors)} test(s) failed")
        sys.exit(1)
    else:
        print("\n✅ All tests passed/skipped")


if __name__ == "__main__":
    main()
