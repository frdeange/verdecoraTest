from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.services.hitl_webform import auth
from src.services.hitl_webform.main import create_app
from src.services.hitl_webform.security import TokenClaims, TokenValidationError

pytestmark = pytest.mark.unit


class FakeReviewStore:
    def __init__(self) -> None:
        self.record = {
            "id": "alb-401",
            "pipeline_result": {
                "validation": {"discrepancies": ["Cantidad pendiente de revisar."]},
            },
        }

    async def get_review_record(self, albaran_id: str) -> dict[str, Any] | None:
        return self.record if albaran_id == self.record["id"] else None

    async def close(self) -> None:
        return None


class FakePublisher:
    async def publish(self, decision: Any) -> None:
        _ = decision

    async def close(self) -> None:
        return None


class FakeValidator:
    def __init__(self, *, claims: TokenClaims | None = None, error: Exception | None = None, allow_role: bool = True) -> None:
        self._claims = claims
        self._error = error
        self._allow_role = allow_role

    async def validate_token(self, token: str) -> TokenClaims:
        _ = token
        if self._error is not None:
            raise self._error
        assert self._claims is not None
        return self._claims

    def require_role(self, claims: TokenClaims, role: str) -> bool:
        _ = claims, role
        return self._allow_role


def _build_claims(*, roles: tuple[str, ...]) -> TokenClaims:
    return TokenClaims.model_validate(
        {
            "sub": "user-123",
            "iss": "https://login.microsoftonline.com/tenant-id/v2.0",
            "aud": "api://verdecora-hitl",
            "email": "encargado@verdecora.es",
            "roles": roles,
            "raw_claims": {"roles": list(roles)},
        }
    )


def test_missing_authorization_header_returns_401() -> None:
    app = create_app(review_store=FakeReviewStore(), decision_publisher=FakePublisher())

    with TestClient(app) as client:
        response = client.get("/review/alb-401")

    assert response.status_code == 401


def test_invalid_jwt_returns_401(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "get_token_validator",
        lambda *_: FakeValidator(error=TokenValidationError("The Entra access token is invalid or expired.")),
    )
    app = create_app(review_store=FakeReviewStore(), decision_publisher=FakePublisher())

    with TestClient(app) as client:
        response = client.get("/review/alb-401", headers={"Authorization": "Bearer invalid.jwt"})

    assert response.status_code == 401


def test_expired_token_returns_401(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "get_token_validator",
        lambda *_: FakeValidator(error=TokenValidationError("The Entra access token is invalid or expired.")),
    )
    app = create_app(review_store=FakeReviewStore(), decision_publisher=FakePublisher())

    with TestClient(app) as client:
        response = client.get("/review/alb-401", headers={"Authorization": "Bearer expired.jwt"})

    assert response.status_code == 401


def test_valid_token_with_wrong_role_returns_403(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "get_token_validator",
        lambda *_: FakeValidator(claims=_build_claims(roles=("Verdecora.Observer",)), allow_role=False),
    )
    app = create_app(review_store=FakeReviewStore(), decision_publisher=FakePublisher())

    with TestClient(app) as client:
        response = client.get("/review/alb-401", headers={"Authorization": "Bearer signed.jwt"})

    assert response.status_code == 403


def test_valid_token_with_required_role_returns_200(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "get_token_validator",
        lambda *_: FakeValidator(claims=_build_claims(roles=("Verdecora.StoreManager",)), allow_role=True),
    )
    app = create_app(review_store=FakeReviewStore(), decision_publisher=FakePublisher())

    with TestClient(app) as client:
        response = client.get("/review/alb-401", headers={"Authorization": "Bearer signed.jwt"})

    assert response.status_code == 200
