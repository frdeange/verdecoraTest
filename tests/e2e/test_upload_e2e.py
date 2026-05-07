"""E2E test: full upload flow from session creation to status check (all mocked)."""

from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient
from itsdangerous import URLSafeSerializer

from src.upload_web.app import create_app
from src.upload_web.config import get_settings
from src.upload_web.services import upload_session

SIGNING_KEY = "dev-only-upload-web-session-signing-key-change-me"

pytestmark = pytest.mark.e2e


def _auth_headers(oid: str = "oid-e2e-flow", name: str = "E2E Flow User") -> dict[str, str]:
    principal = {
        "auth_typ": "aad",
        "claims": [
            {
                "typ": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier",
                "val": oid,
            },
            {"typ": "name", "val": name},
            {"typ": "preferred_username", "val": f"{oid}@verdecora.example"},
            {"typ": "groups", "val": "verdecora-store-uploaders"},
            {"typ": "exp", "val": "9999999999"},
        ],
        "name_typ": "name",
        "role_typ": "roles",
    }
    encoded_principal = base64.b64encode(json.dumps(principal).encode("utf-8")).decode("utf-8")
    return {
        "X-MS-CLIENT-PRINCIPAL": encoded_principal,
        "X-MS-CLIENT-PRINCIPAL-ID": oid,
        "X-MS-CLIENT-PRINCIPAL-NAME": name,
        "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
    }


def _establish_session(client: TestClient, oid: str = "oid-e2e-flow", name: str = "E2E Flow User") -> dict[str, str]:
    headers = _auth_headers(oid, name)
    client.get("/", headers=headers)
    cookie_value = client.cookies.get("upload_web_session", "")
    if cookie_value:
        serializer = URLSafeSerializer(SIGNING_KEY, salt="upload-web-session")
        payload = serializer.loads(cookie_value)
        headers["X-CSRF-Token"] = payload.get("csrf_token", "")
    return headers


def _api_client() -> TestClient:
    return TestClient(create_app(), base_url="https://testserver")


@pytest.fixture(autouse=True)
def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STORAGE_ACCOUNT_URL", raising=False)
    monkeypatch.delenv("BLOB_ACCOUNT", raising=False)
    upload_session.clear_upload_sessions()
    yield
    upload_session.clear_upload_sessions()
    get_settings.cache_clear()


def test_full_upload_flow_e2e() -> None:
    """Full E2E flow: create session → generate SAS → register file → preflight → confirm → check status."""
    with _api_client() as client:
        headers = _establish_session(client)

        # 1. Create session
        create_resp = client.post("/api/sessions", headers=headers)
        assert create_resp.status_code == 201
        session_data = create_resp.json()
        session_id = session_data["session_id"]
        assert session_data["status"] == "created"

        # 2. Generate SAS URL
        sas_resp = client.post(f"/api/sessions/{session_id}/sas?filename=albaran_001.pdf", headers=headers)
        assert sas_resp.status_code == 200
        sas_body = sas_resp.json()
        assert "upload_url" in sas_body
        assert "mock" in sas_body["upload_url"]
        assert sas_body["blob_path"] == f"{session_id}/albaran_001.pdf"

        # 3. Register file (simulate successful blob upload)
        reg_resp = client.post(
            f"/api/sessions/{session_id}/files",
            headers=headers,
            json={
                "filename": "albaran_001.pdf",
                "blob_path": f"{session_id}/albaran_001.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 4096,
                "albaran_group": "group-A",
                "page_number": 1,
            },
        )
        assert reg_resp.status_code == 201
        assert reg_resp.json()["status"] == "registered"

        # Register a second file in the same group
        reg_resp2 = client.post(
            f"/api/sessions/{session_id}/files",
            headers=headers,
            json={
                "filename": "albaran_002.pdf",
                "blob_path": f"{session_id}/albaran_002.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 3072,
                "albaran_group": "group-A",
                "page_number": 2,
            },
        )
        assert reg_resp2.status_code == 201

        # 4. Preflight
        pf_resp = client.post(f"/api/sessions/{session_id}/preflight", headers=headers)
        assert pf_resp.status_code == 200
        pf_body = pf_resp.json()
        assert "confidence" in pf_body
        assert pf_body["session_id"] == session_id

        # 5. Confirm
        confirm_resp = client.post(f"/api/sessions/{session_id}/confirm", headers=headers)
        assert confirm_resp.status_code == 200
        assert confirm_resp.json()["status"] == "confirmed"

        # 6. Check status
        status_resp = client.get(f"/api/sessions/{session_id}/status", headers=headers)
        assert status_resp.status_code == 200
        status_body = status_resp.json()
        assert status_body["session_id"] == session_id
        assert status_body["total_files"] == 2
        assert status_body["status"] == "confirmed"
        assert len(status_body["files"]) == 2
        assert status_body["files"][0]["albaran_group"] == "group-A"


def test_e2e_reject_bad_mime() -> None:
    """E2E: file with bad MIME type is rejected at registration."""
    with _api_client() as client:
        headers = _establish_session(client)
        create_resp = client.post("/api/sessions", headers=headers)
        session_id = create_resp.json()["session_id"]

        resp = client.post(
            f"/api/sessions/{session_id}/files",
            headers=headers,
            json={
                "filename": "virus.exe",
                "blob_path": f"{session_id}/virus.exe",
                "mime_type": "application/x-executable",
                "size_bytes": 1024,
            },
        )
        assert resp.status_code == 422


def test_e2e_confirm_empty_session_fails() -> None:
    """E2E: cannot confirm a session with no files."""
    with _api_client() as client:
        headers = _establish_session(client)
        create_resp = client.post("/api/sessions", headers=headers)
        session_id = create_resp.json()["session_id"]

        resp = client.post(f"/api/sessions/{session_id}/confirm", headers=headers)
        assert resp.status_code == 400
