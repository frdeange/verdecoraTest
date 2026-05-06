from __future__ import annotations

import logging
import re
from typing import Any

from src.upload_web.models.preflight import PageGroup, PreflightResult
from src.upload_web.models.upload import UploadSession
from src.upload_web.services.store_detector import detect_store_from_catalog

logger = logging.getLogger(__name__)

_DATE_PATTERN = re.compile(r"\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b")
_ALBARAN_NUMBER_PATTERN = re.compile(
    r"(?:albar[aá]n|n[ºo°]?\s*:?\s*|ref\.?\s*:?\s*)(\w[\w\-/]*\d+)",
    re.IGNORECASE,
)

# Confidence thresholds
AUTO_CONFIRM_THRESHOLD = 0.85
MANUAL_REVIEW_THRESHOLD = 0.5


def _extract_text_from_results(doc_intelligence_results: list[dict[str, Any]] | None) -> str:
    """Combine text content from Document Intelligence results."""
    if not doc_intelligence_results:
        return ""
    parts: list[str] = []
    for result in doc_intelligence_results:
        content = result.get("content", "")
        if isinstance(content, str):
            parts.append(content)
    return "\n".join(parts)


def _compute_confidence(
    is_albaran: bool,
    detected_supplier: str | None,
    detected_date: str | None,
    store_confidence: float,
) -> float:
    """Compute overall confidence score from extracted signals."""
    confidence = store_confidence
    if is_albaran:
        confidence = min(confidence + 0.5, 1.0)
    if detected_supplier:
        confidence = min(confidence + 0.15, 1.0)
    if detected_date:
        confidence = min(confidence + 0.1, 1.0)
    return confidence


def run_preflight(
    session: UploadSession,
    doc_intelligence_results: list[dict[str, Any]] | None = None,
) -> PreflightResult:
    """Analyse uploaded files and extract heuristic metadata."""
    warnings: list[str] = []
    files_analyzed = len(session.files)
    full_text = _extract_text_from_results(doc_intelligence_results)

    if not full_text.strip():
        warnings.append("No text could be extracted from the uploaded documents. Preflight analysis is limited.")
        confidence = 0.1 if files_analyzed > 0 else 0.0
        if confidence < MANUAL_REVIEW_THRESHOLD:
            warnings.append("Low confidence — manual review recommended.")
        return PreflightResult(
            session_id=session.session_id,
            files_analyzed=files_analyzed,
            confidence=round(confidence, 2),
            warnings=warnings,
        )

    detected_date = _extract_date(full_text)
    detected_albaran_number = _extract_albaran_number(full_text)
    detected_supplier = _extract_supplier(full_text, doc_intelligence_results or [])

    store_match = detect_store_from_catalog(full_text)
    detected_store = store_match.store.name if store_match.store is not None else None
    store_confidence = (store_match.confidence * 0.5) if store_match.store is not None else 0.0

    is_albaran = detected_albaran_number is not None or _text_looks_like_albaran(full_text)
    confidence = _compute_confidence(is_albaran, detected_supplier, detected_date, store_confidence)

    page_groups: list[PageGroup] = []
    if files_analyzed > 1:
        page_groups = [
            PageGroup(
                group_id="group-1",
                page_indices=list(range(files_analyzed)),
                suggested_supplier=detected_supplier,
                suggested_date=detected_date,
                suggested_albaran_number=detected_albaran_number,
            )
        ]

    if confidence < MANUAL_REVIEW_THRESHOLD:
        warnings.append("Low confidence — manual review recommended.")

    return PreflightResult(
        session_id=session.session_id,
        files_analyzed=files_analyzed,
        detected_supplier=detected_supplier,
        detected_date=detected_date,
        detected_albaran_number=detected_albaran_number,
        detected_store=detected_store,
        confidence=round(confidence, 2),
        is_albaran=is_albaran,
        warnings=warnings,
        page_groups=page_groups,
    )


def analyze_with_document_intelligence(
    blob_url: str,
    endpoint: str,
) -> dict[str, Any]:
    """Call Azure Document Intelligence prebuilt-layout on a blob.

    Returns the raw analysis result dict.  Requires ``azure-ai-documentintelligence``.
    """
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.ai.documentintelligence.models import AnalyzeDocumentRequest

    from src.config.security import get_managed_identity_credential

    credential = get_managed_identity_credential()
    client = DocumentIntelligenceClient(endpoint=endpoint, credential=credential)

    poller = client.begin_analyze_document(
        "prebuilt-layout",
        AnalyzeDocumentRequest(url_source=blob_url),
    )
    result = poller.result()
    return {"content": result.content if result.content else ""}


# ── private helpers ──────────────────────────────────────────────────


def _extract_date(text: str) -> str | None:
    match = _DATE_PATTERN.search(text)
    return match.group(1) if match else None


def _extract_albaran_number(text: str) -> str | None:
    match = _ALBARAN_NUMBER_PATTERN.search(text)
    return match.group(1) if match else None


def _extract_supplier(text: str, results: list[dict[str, Any]]) -> str | None:
    """Best-effort supplier extraction from first lines of text."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:5]:
        if len(line) > 3 and not line[0].isdigit() and "albar" not in line.lower():
            return line
    return None


def _text_looks_like_albaran(text: str) -> bool:
    lower = text.lower()
    keywords = ["albarán", "albaran", "delivery note", "nota de entrega", "nº albarán"]
    return any(kw in lower for kw in keywords)


__all__ = [
    "AUTO_CONFIRM_THRESHOLD",
    "MANUAL_REVIEW_THRESHOLD",
    "analyze_with_document_intelligence",
    "run_preflight",
]
