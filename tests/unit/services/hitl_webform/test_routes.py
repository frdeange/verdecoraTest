from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

import src.services.hitl_webform.routes as routes
from src.services.hitl_webform.auth import AuthenticatedReviewer
from src.services.hitl_webform.main import create_app


class FakeReviewStore:
    def __init__(self) -> None:
        self.record = {
            "id": "alb-003",
            "pipeline_result": {
                "extraction": {"header": {"document_number": "ALB-003", "supplier_name": "Royal Canin"}},
                "validation": {
                    "discrepancies": ["Cantidad distinta en la línea 1."],
                    "line_comparisons": [
                        {
                            "line_number": 1,
                            "field": "quantity",
                            "extracted_value": "5",
                            "bc_value": "4",
                            "status": "mismatch",
                        }
                    ],
                },
            },
        }
        self.saved_decisions: list[dict[str, Any]] = []

    async def get_review_record(self, albaran_id: str) -> dict[str, Any] | None:
        return self.record if albaran_id == self.record["id"] else None

    async def save_decision(self, decision: Any) -> dict[str, Any]:
        payload = decision.model_dump(mode="json")
        self.saved_decisions.append(payload)
        return payload


class FakePublisher:
    def __init__(self) -> None:
        self.decisions: list[dict[str, Any]] = []

    async def publish(self, decision: Any) -> None:
        self.decisions.append(decision.model_dump(mode="json"))


async def _fake_validate_entra_token(*_: Any, **__: Any) -> AuthenticatedReviewer:
    return AuthenticatedReviewer(
        email="reviewer@verdecora.example.com",
        subject="reviewer-123",
        display_name="Reviewer",
        roles=("Verdecora.StoreManager",),
    )


def test_hitl_webform_routes_render_review_and_publish_decision(monkeypatch) -> None:
    monkeypatch.setattr(routes, "validate_entra_token", _fake_validate_entra_token)
    store = FakeReviewStore()
    publisher = FakePublisher()
    app = create_app(review_store=store, decision_publisher=publisher)

    with TestClient(app) as client:
        health_response = client.get("/health")
        review_response = client.get(
            "/review/alb-003",
            headers={"Authorization": "Bearer signed.jwt"},
        )
        decision_response = client.post(
            "/review/alb-003/decide",
            headers={"Authorization": "Bearer signed.jwt"},
            json={
                "decision": "modify",
                "modified_lines": [{"line_number": 1, "quantity": 4}],
                "notes": "Ajustado según BC.",
            },
        )

    assert health_response.json() == {"status": "ok"}
    assert review_response.status_code == 200
    assert "Cantidad distinta en la línea 1." in review_response.text
    assert decision_response.status_code == 200
    assert decision_response.json()["decision"]["reviewer_email"] == "reviewer@verdecora.example.com"
    assert store.saved_decisions[0]["decision"] == "modify"
    assert publisher.decisions[0]["notes"] == "Ajustado según BC."
