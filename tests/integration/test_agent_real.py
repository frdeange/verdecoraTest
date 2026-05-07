from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TypeVar

import pytest
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI
from pydantic import BaseModel

from src.agents.prompts import build_extractor_instructions, build_triage_instructions
from src.models.albaran import AlbaranExtraction, DocumentType, TriageResult

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_AGENT_REAL_INTEGRATION", "").lower() not in {"1", "true", "yes", "on"},
        reason="Real OCR + agent integration disabled. Set RUN_AGENT_REAL_INTEGRATION=1 to enable.",
    ),
]

DOCINTELL_ENDPOINT = os.getenv(
    "DOCINTELL_ENDPOINT",
    "https://verdecora-docintell-dev.cognitiveservices.azure.com/",
)
AZURE_AI_ENDPOINT = os.getenv(
    "AZURE_AI_ENDPOINT",
    "https://verdecora-ais-dev.cognitiveservices.azure.com/",
)
API_VERSION = "2025-01-01-preview"
GPT5_DEPLOYMENT = os.getenv("GPT5_DEPLOYMENT", "gpt-5")
GPT5_MINI_DEPLOYMENT = os.getenv("GPT5_MINI_DEPLOYMENT", "gpt-5-mini")
OCR_PAGE_LIMIT = int(os.getenv("AGENT_REAL_OCR_PAGE_LIMIT", "1"))
ROOT_DIR = Path(__file__).resolve().parents[2]
PDF_CANDIDATES = (
    ROOT_DIR / "data" / "PRUEBA.pdf",
    ROOT_DIR / "tests" / "fixtures" / "PRUEBA.pdf",
    ROOT_DIR / "prerequisites" / "PRUEBA.pdf",
)

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


def _resolve_pdf_path() -> Path:
    for path in PDF_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError(
        "No test PDF found. Expected PRUEBA.pdf under data/, tests/fixtures/, or prerequisites/."
    )


def _get_credential() -> DefaultAzureCredential:
    return DefaultAzureCredential()


def _get_docintell_client(credential: DefaultAzureCredential) -> DocumentIntelligenceClient:
    return DocumentIntelligenceClient(endpoint=DOCINTELL_ENDPOINT, credential=credential)


def _get_openai_client(credential: DefaultAzureCredential) -> AzureOpenAI:
    token_provider = get_bearer_token_provider(
        credential,
        "https://cognitiveservices.azure.com/.default",
    )
    return AzureOpenAI(
        azure_endpoint=AZURE_AI_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version=API_VERSION,
    )


def _extract_raw_text(result: object, *, page_limit: int | None = None) -> str:
    pages = getattr(result, "pages", None) or []
    page_chunks: list[str] = []
    selected_pages = pages[:page_limit] if page_limit is not None else pages
    for page in selected_pages:
        lines = getattr(page, "lines", None) or []
        page_number = getattr(page, "page_number", "?")
        page_text = "\n".join(line.content for line in lines if getattr(line, "content", None))
        if page_text:
            page_chunks.append(f"=== Page {page_number} ===\n{page_text}")

    if page_chunks:
        return "\n\n".join(page_chunks)

    content = getattr(result, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()

    paragraphs = getattr(result, "paragraphs", None) or []
    return "\n".join(paragraph.content for paragraph in paragraphs if getattr(paragraph, "content", None)).strip()


def _clean_json_content(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return cleaned


def _normalize_language(language: str) -> str:
    normalized = language.strip().lower()
    aliases = {
        "spanish": "es",
        "español": "es",
        "espanol": "es",
        "italian": "it",
        "italiano": "it",
        "german": "de",
        "deutsch": "de",
        "english": "en",
        "inglés": "en",
        "ingles": "en",
    }
    return aliases.get(normalized, normalized)


def _run_structured_completion(
    client: AzureOpenAI,
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    response_model: type[StructuredModel],
    max_completion_tokens: int,
) -> StructuredModel:
    attempt_prompts = [
        user_prompt,
        f"{user_prompt}\n\nResponde solo con un objeto JSON válido, sin markdown ni texto adicional.",
    ]
    last_error: Exception | None = None
    last_content = ""

    for attempt_prompt in attempt_prompts:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": attempt_prompt},
            ],
            max_completion_tokens=max_completion_tokens,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or ""
        last_content = content

        try:
            cleaned = _clean_json_content(content)
            if not cleaned:
                raise AssertionError("Model returned empty content")
            payload = json.loads(cleaned)
            return response_model.model_validate(payload)
        except (AssertionError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc

    raise AssertionError(f"Structured completion failed: {last_error}. Raw content: {last_content[:500]}")


@pytest.fixture(scope="session")
def real_ocr_payload() -> dict[str, object]:
    pdf_path = _resolve_pdf_path()
    credential = _get_credential()
    client = _get_docintell_client(credential)

    with pdf_path.open("rb") as handle:
        pdf_bytes = handle.read()

    poller = client.begin_analyze_document(
        "prebuilt-layout",
        body=pdf_bytes,
        content_type="application/pdf",
    )
    result = poller.result()
    raw_text = _extract_raw_text(result, page_limit=OCR_PAGE_LIMIT)

    print(f"\n{'=' * 70}")
    print("A1/A2 real OCR input")
    print(f"{'=' * 70}")
    print(f"PDF: {pdf_path}")
    print(f"Pages selected: {min(len(result.pages or []), OCR_PAGE_LIMIT)} / {len(result.pages or [])}")
    print(f"Tables: {len(result.tables or [])}")
    print(f"Paragraphs: {len(result.paragraphs or [])}")
    print(f"OCR preview:\n{raw_text[:1200]}")

    assert raw_text.strip(), "Document Intelligence returned empty OCR text"

    return {
        "pdf_path": pdf_path,
        "raw_text": raw_text,
        "page_count": min(len(result.pages or []), OCR_PAGE_LIMIT),
    }


@pytest.fixture(scope="session")
def real_extraction(real_ocr_payload: dict[str, object]) -> AlbaranExtraction:
    credential = _get_credential()
    client = _get_openai_client(credential)
    raw_text = str(real_ocr_payload["raw_text"])

    extraction = _run_structured_completion(
        client,
        model=GPT5_DEPLOYMENT,
        system_prompt=build_extractor_instructions(),
        user_prompt=(
            "Extrae un único albarán a partir del siguiente OCR real de Azure Document Intelligence.\n\n"
            f"{raw_text}"
        ),
        response_model=AlbaranExtraction,
        max_completion_tokens=8000,
    )

    print(f"\n{'=' * 70}")
    print("A1 Extractor result")
    print(f"{'=' * 70}")
    print(json.dumps(extraction.model_dump(mode="json"), ensure_ascii=False, indent=2))

    return extraction


@pytest.fixture(scope="session")
def real_triage(real_ocr_payload: dict[str, object]) -> TriageResult:
    credential = _get_credential()
    client = _get_openai_client(credential)
    raw_text = str(real_ocr_payload["raw_text"])

    triage = _run_structured_completion(
        client,
        model=GPT5_MINI_DEPLOYMENT,
        system_prompt=build_triage_instructions(),
        user_prompt=(
            "Clasifica y enruta el siguiente OCR real de un único documento escaneado.\n\n"
            f"{raw_text}"
        ),
        response_model=TriageResult,
        max_completion_tokens=1500,
    )

    print(f"\n{'=' * 70}")
    print("A2 Triage result")
    print(f"{'=' * 70}")
    print(json.dumps(triage.model_dump(mode="json"), ensure_ascii=False, indent=2))

    return triage


def test_real_extractor_pipeline(real_extraction: AlbaranExtraction) -> None:
    assert real_extraction.header.supplier_name.strip()
    assert real_extraction.header.document_date or real_extraction.header.delivery_date
    assert real_extraction.line_items
    assert any(item.quantity > 0 for item in real_extraction.line_items)
    assert any(item.unit_price is not None or item.total is not None for item in real_extraction.line_items)
    assert real_extraction.source_pages or real_extraction.raw_text is not None
    assert real_extraction.confidence_score >= 0.5


def test_real_triage_pipeline(real_triage: TriageResult) -> None:
    assert real_triage.document_type is not DocumentType.UNKNOWN
    assert _normalize_language(real_triage.language) == "es"
    assert real_triage.routing_decision == "extract"
    assert real_triage.confidence >= 0.5
    assert real_triage.reasoning.strip()


def main() -> int:
    os.environ.setdefault("RUN_AGENT_REAL_INTEGRATION", "1")
    return pytest.main([__file__, "-s", "-v"])


if __name__ == "__main__":
    raise SystemExit(main())
