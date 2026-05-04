from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.hitl_webform import security  # noqa: E402


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_token_uses_jwks_and_extracts_claims(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeSigningKey:
        key = "signing-key"

    class FakePyJWKClient:
        def __init__(self, jwks_url: str) -> None:
            captured["jwks_url"] = jwks_url

        def get_signing_key_from_jwt(self, token: str) -> FakeSigningKey:
            captured["token"] = token
            return FakeSigningKey()

    def fake_decode(
        token: str,
        key: str,
        *,
        algorithms: list[str],
        audience: str,
        issuer: str,
        options: dict[str, object],
    ) -> dict[str, object]:
        captured["decoded_with"] = {
            "token": token,
            "key": key,
            "algorithms": algorithms,
            "audience": audience,
            "issuer": issuer,
            "options": options,
        }
        return {
            "sub": "user-123",
            "iss": issuer,
            "aud": audience,
            "preferred_username": "Encargado@Verdecora.es",
            "roles": ["Verdecora.StoreManager", "Verdecora.Observer"],
            "exp": 9999999999,
            "iat": 1,
            "nbf": 1,
        }

    monkeypatch.setattr(security, "PyJWKClient", FakePyJWKClient)
    monkeypatch.setattr(security.jwt, "decode", fake_decode)

    validator = security.EntraTokenValidator(tenant_id="tenant-id", client_id="client-id")
    claims = await validator.validate_token("header.payload.signature")

    assert captured["jwks_url"] == "https://login.microsoftonline.com/tenant-id/v2.0/discovery/v2.0/keys"
    assert claims.email == "encargado@verdecora.es"
    assert claims.roles == ("Verdecora.StoreManager", "Verdecora.Observer")
    assert validator.require_role(claims, "verdecora.storemanager") is True


@pytest.mark.unit
def test_extract_bearer_token_requires_expected_header_format() -> None:
    assert security.extract_bearer_token("Bearer signed.jwt") == "signed.jwt"

    with pytest.raises(security.TokenValidationError):
        security.extract_bearer_token("Basic abc123")
