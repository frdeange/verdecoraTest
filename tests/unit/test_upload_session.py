from __future__ import annotations

import base64
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from itsdangerous import URLSafeSerializer

from src.upload_web.app import create_app
from src.upload_web.config import get_settings
from src.upload_web.services import upload_session

SIGNING_KEY = "dev-only-upload-web-session-signing-key-change-me"


@pytest.fixture(autouse=True)
def clear_sessions() -> None:
    upload_session.clear_upload_sessions()
    yield
    upload_session.clear_upload_sessions()
    get_settings.cache_clear()


def _auth_headers(name: str = "Parker Store") -> dict[str, str]:
    principal = {
        "auth_typ": "aad",
        "claims": [
            {
                "typ": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier",
                "val": "oid-123",
            },
            {"typ": "name", "val": name},
            {"typ": "preferred_username", "val": f"{name.lower().replace(' ', '.')}@verdecora.example"},
            {"typ": "groups", "val": "verdecora-store-uploaders"},
            {"typ": "exp", "val": "9999999999"},
        ],
        "name_typ": "name",
        "role_typ": "roles",
    }
    encoded_principal = base64.b64encode(json.dumps(principal).encode("utf-8")).decode("utf-8")
    return {
        "X-MS-CLIENT-PRINCIPAL": encoded_principal,
        "X-MS-CLIENT-PRINCIPAL-ID": "oid-123",
        "X-MS-CLIENT-PRINCIPAL-NAME": name,
        "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
    }


def _establish_session(client: TestClient, name: str = "Parker Store") -> dict[str, str]:
    headers = _auth_headers(name)
    client.get("/", headers=headers)
    cookie_value = client.cookies.get("upload_web_session", "")
    if cookie_value:
        serializer = URLSafeSerializer(SIGNING_KEY, salt="upload-web-session")
        payload = serializer.loads(cookie_value)
        headers["X-CSRF-Token"] = payload.get("csrf_token", "")
    return headers


@pytest.mark.unit
def test_create_upload_session_returns_mock_sas_when_storage_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STORAGE_ACCOUNT_URL", raising=False)
    monkeypatch.delenv("BLOB_ACCOUNT", raising=False)

    session = upload_session.create_upload_session(user_oid="oid-123", user_name="Parker Store")

    assert session.user_oid == "oid-123"
    assert session.user_name == "Parker Store"
    assert session.status == "created"
    assert session.upload_prefix == f"{session.session_id}/"
    assert session.sas_token.startswith(f"mock-sas-session={session.session_id}")
    assert upload_session.get_upload_session(session.session_id) == session


@pytest.mark.unit
def test_create_upload_session_uses_container_sas_when_storage_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeBlobServiceClient:
        def __init__(self, *, account_url: str, credential: object) -> None:
            captured["account_url"] = account_url
            captured["credential"] = credential
            self.account_name = "stverdecora"

        def get_user_delegation_key(self, start: datetime, expiry: datetime) -> str:
            captured["delegation_window"] = (start, expiry)
            return "delegation-key"

    class FakeContainerSasPermissions:
        def __init__(self, *, read: bool, write: bool, create: bool) -> None:
            captured["permissions"] = {"read": read, "write": write, "create": create}

    def fake_generate_container_sas(**kwargs: object) -> str:
        captured["sas_kwargs"] = kwargs
        return "sig=real-token"

    credential = object()
    monkeypatch.setenv("STORAGE_ACCOUNT_URL", "https://stverdecora.blob.core.windows.net")
    monkeypatch.setattr(upload_session, "BlobServiceClient", FakeBlobServiceClient)
    monkeypatch.setattr(upload_session, "ContainerSasPermissions", FakeContainerSasPermissions)
    monkeypatch.setattr(upload_session, "generate_container_sas", fake_generate_container_sas)
    monkeypatch.setattr(upload_session, "get_managed_identity_credential", lambda: credential)

    session = upload_session.create_upload_session(user_oid="oid-123", user_name="Parker Store")

    assert session.sas_token == "sig=real-token"
    assert captured["account_url"] == "https://stverdecora.blob.core.windows.net"
    assert captured["credential"] is credential
    assert captured["permissions"] == {"read": True, "write": True, "create": True}
    assert captured["sas_kwargs"]["container_name"] == "albaranes-raw"
    assert captured["sas_kwargs"]["user_delegation_key"] == "delegation-key"


@pytest.mark.unit
def test_get_upload_session_returns_none_for_unknown_id() -> None:
    assert upload_session.get_upload_session("missing-session") is None


@pytest.mark.unit
def test_api_creates_and_reads_upload_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STORAGE_ACCOUNT_URL", raising=False)
    monkeypatch.delenv("BLOB_ACCOUNT", raising=False)
    app = create_app()

    with TestClient(app, base_url="https://testserver") as client:
        headers = _establish_session(client)
        create_response = client.post("/api/sessions", headers=headers)
        assert create_response.status_code == 201
        created_session = create_response.json()

        read_response = client.get(f"/api/sessions/{created_session['session_id']}", headers=headers)

    assert read_response.status_code == 200
    assert read_response.json()["session_id"] == created_session["session_id"]
    assert read_response.json()["user_name"] == "Parker Store"
