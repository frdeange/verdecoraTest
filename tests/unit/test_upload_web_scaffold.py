from __future__ import annotations

import jwt
import pytest
from fastapi.testclient import TestClient

from src.shared.auth.dependencies import get_current_user
from src.upload_web.app import create_app
from src.upload_web.config import get_settings


@pytest.mark.unit
def test_upload_web_healthz_returns_ok() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.unit
def test_upload_web_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLOB_ACCOUNT", "https://blob.verdecora.example")
    monkeypatch.setenv("COSMOS_URL", "https://cosmos.verdecora.example")
    monkeypatch.setenv("APP_INSIGHTS_CONNECTION_STRING", "InstrumentationKey=test-key")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.blob_account == "https://blob.verdecora.example"
    assert settings.cosmos_url == "https://cosmos.verdecora.example"
    assert settings.app_insights_connection_string == "InstrumentationKey=test-key"
    get_settings.cache_clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_entra_auth_dependency_extracts_user_from_token() -> None:
    token = jwt.encode(
        {
            "oid": "oid-123",
            "name": "Alice Upload",
            "groups": ["verdecora-store-uploaders", "ops"],
            "exp": 9999999999,
        },
        "test-secret-with-at-least-thirty-two-bytes",
        algorithm="HS256",
    )

    user = await get_current_user(x_ms_token_aad_id_token=token)

    assert user.oid == "oid-123"
    assert user.name == "Alice Upload"
    assert user.groups == ("verdecora-store-uploaders", "ops")
