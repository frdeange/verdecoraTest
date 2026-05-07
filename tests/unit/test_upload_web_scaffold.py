from __future__ import annotations

import base64
import json

import pytest
from fastapi import Request
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
    principal = {
        "auth_typ": "aad",
        "claims": [
            {
                "typ": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier",
                "val": "oid-123",
            },
            {"typ": "name", "val": "Alice Upload"},
            {"typ": "preferred_username", "val": "alice.upload@verdecora.example"},
            {"typ": "groups", "val": "verdecora-store-uploaders"},
            {"typ": "groups", "val": "ops"},
            {"typ": "exp", "val": "9999999999"},
        ],
        "name_typ": "name",
        "role_typ": "roles",
    }
    encoded_principal = base64.b64encode(json.dumps(principal).encode("utf-8")).decode("utf-8")
    request = Request(
        {
            "type": "http",
            "headers": [
                (b"x-ms-client-principal", encoded_principal.encode("utf-8")),
                (b"x-ms-client-principal-id", b"oid-123"),
                (b"x-ms-client-principal-name", b"Alice Upload"),
                (b"x-ms-client-principal-idp", b"aad"),
            ],
        }
    )

    user = await get_current_user(request)

    assert user.oid == "oid-123"
    assert user.name == "Alice Upload"
    assert user.groups == ("verdecora-store-uploaders", "ops")
