from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.hitl_webform.audit import AuditLogger, HITLDecision  # noqa: E402


class FakeContainer:
    def __init__(self) -> None:
        self.documents: list[dict[str, object]] = []

    async def upsert_item(self, body: dict[str, object]) -> None:
        self.documents.append(body)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_log_decision_persists_structured_audit_record() -> None:
    container = FakeContainer()
    logger = AuditLogger(container_client=container)

    await logger.log_decision(
        HITLDecision(
            albaran_id="ALB-001",
            action="approve",
            reviewer_email="Manager@Verdecora.es",
            comment="Mercancía correcta",
            store_id="MAD-001",
        ),
        reviewer_ip="10.0.0.5",
        correlation_id="corr-001",
    )

    assert container.documents[0]["pk"] == "ALB-001"
    assert container.documents[0]["eventType"] == "hitl.decision"
    assert container.documents[0]["reviewerEmail"] == "manager@verdecora.es"
    assert container.documents[0]["correlationId"] == "corr-001"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_log_pdf_access_persists_sas_access_audit_record() -> None:
    container = FakeContainer()
    logger = AuditLogger(container_client=container)

    await logger.log_pdf_access("ALB-002", "Store.Manager@Verdecora.es", "corr-002")

    assert container.documents[0]["eventType"] == "hitl.pdf_access"
    assert container.documents[0]["userEmail"] == "store.manager@verdecora.es"
    assert container.documents[0]["albaranId"] == "ALB-002"
