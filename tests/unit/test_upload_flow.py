"""Tests for Upload Web Wave 2 flow: SAS, file registration, validation, preflight, session lifecycle, ownership."""

from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient
from itsdangerous import URLSafeSerializer

from src.upload_web.app import create_app
from src.upload_web.config import get_settings
from src.upload_web.services import upload_session
from src.upload_web.services.blob_sas import generate_upload_sas_url
from src.upload_web.services.file_validator import validate_file

SIGNING_KEY = "dev-only-upload-web-session-signing-key-change-me"


def _auth_headers(oid: str = "oid-flow-001", name: str = "Flow Test User") -> dict[str, str]:
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


def _establish_session(client: TestClient, oid: str = "oid-flow-001", name: str = "Flow Test User") -> dict[str, str]:
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


# ── SAS URL generation (mock mode) ──────────────────────────────────


@pytest.mark.unit
def test_sas_url_mock_contains_session_id() -> None:
    sas_url, blob_path, expires_in = generate_upload_sas_url("sess-001", "albaran.pdf")
    assert "mock" in sas_url.lower()
    assert "sess-001" in sas_url
    assert blob_path == "sess-001/albaran.pdf"
    assert expires_in == 900


@pytest.mark.unit
def test_sas_url_mock_different_filenames() -> None:
    url1, path1, _ = generate_upload_sas_url("s1", "file_a.pdf")
    url2, path2, _ = generate_upload_sas_url("s1", "file_b.jpg")
    assert path1 == "s1/file_a.pdf"
    assert path2 == "s1/file_b.jpg"
    assert url1 != url2


# ── File metadata registration ──────────────────────────────────────


@pytest.mark.unit
def test_register_file_valid_payload() -> None:
    with _api_client() as client:
        headers = _establish_session(client)
        create_resp = client.post("/api/sessions", headers=headers)
        session_id = create_resp.json()["session_id"]

        resp = client.post(
            f"/api/sessions/{session_id}/files",
            headers=headers,
            json={
                "filename": "albaran.pdf",
                "blob_path": f"{session_id}/albaran.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 2048,
            },
        )
    assert resp.status_code == 201
    assert resp.json()["status"] == "registered"
    assert "file_id" in resp.json()


@pytest.mark.unit
def test_register_file_invalid_no_filename() -> None:
    with _api_client() as client:
        headers = _establish_session(client)
        create_resp = client.post("/api/sessions", headers=headers)
        session_id = create_resp.json()["session_id"]

        resp = client.post(
            f"/api/sessions/{session_id}/files",
            headers=headers,
            json={
                "blob_path": f"{session_id}/test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 100,
            },
        )
    assert resp.status_code == 422


# ── MIME validation ─────────────────────────────────────────────────


@pytest.mark.unit
def test_mime_accept_pdf() -> None:
    result = validate_file("test.pdf", "application/pdf", 1024)
    assert result.valid is True


@pytest.mark.unit
def test_mime_accept_jpeg() -> None:
    result = validate_file("photo.jpg", "image/jpeg", 2048)
    assert result.valid is True


@pytest.mark.unit
def test_mime_accept_png() -> None:
    result = validate_file("scan.png", "image/png", 3072)
    assert result.valid is True


@pytest.mark.unit
def test_mime_accept_tiff() -> None:
    result = validate_file("scan.tiff", "image/tiff", 4096)
    assert result.valid is True


@pytest.mark.unit
def test_mime_reject_exe() -> None:
    result = validate_file("malware.exe", "application/x-executable", 1024)
    assert result.valid is False
    assert any("not allowed" in e for e in result.errors)


@pytest.mark.unit
def test_mime_reject_zip() -> None:
    result = validate_file("archive.zip", "application/zip", 1024)
    assert result.valid is False


# ── Size validation ─────────────────────────────────────────────────


@pytest.mark.unit
def test_size_under_limit() -> None:
    result = validate_file("ok.pdf", "application/pdf", 10 * 1024 * 1024)
    assert result.valid is True


@pytest.mark.unit
def test_size_over_limit() -> None:
    result = validate_file("huge.pdf", "application/pdf", 60 * 1024 * 1024)
    assert result.valid is False
    assert any("50 MB" in e for e in result.errors)


# ── Preflight endpoint ──────────────────────────────────────────────


@pytest.mark.unit
def test_preflight_returns_result_structure() -> None:
    with _api_client() as client:
        headers = _establish_session(client)
        create_resp = client.post("/api/sessions", headers=headers)
        session_id = create_resp.json()["session_id"]

        client.post(
            f"/api/sessions/{session_id}/files",
            headers=headers,
            json={
                "filename": "test.pdf",
                "blob_path": f"{session_id}/test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )

        resp = client.post(f"/api/sessions/{session_id}/preflight", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert "confidence" in body
    assert "session_id" in body
    assert "is_albaran" in body
    assert "warnings" in body


# ── Session lifecycle ───────────────────────────────────────────────


@pytest.mark.unit
def test_session_lifecycle_created_to_confirmed() -> None:
    with _api_client() as client:
        headers = _establish_session(client)

        # created
        create_resp = client.post("/api/sessions", headers=headers)
        assert create_resp.status_code == 201
        session_id = create_resp.json()["session_id"]
        assert create_resp.json()["status"] == "created"

        # uploading (SAS generation transitions)
        client.post(f"/api/sessions/{session_id}/sas?filename=a.pdf", headers=headers)

        # register file
        client.post(
            f"/api/sessions/{session_id}/files",
            headers=headers,
            json={
                "filename": "a.pdf",
                "blob_path": f"{session_id}/a.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )

        # preflight
        pf_resp = client.post(f"/api/sessions/{session_id}/preflight", headers=headers)
        assert pf_resp.status_code == 200

        # Check session is in preflight state
        get_resp = client.get(f"/api/sessions/{session_id}", headers=headers)
        assert get_resp.json()["status"] == "preflight"

        # confirm
        confirm_resp = client.post(f"/api/sessions/{session_id}/confirm", headers=headers)
        assert confirm_resp.status_code == 200
        assert confirm_resp.json()["status"] == "confirmed"


# ── Session ownership ──────────────────────────────────────────────


@pytest.mark.unit
def test_session_ownership_user_a_cannot_access_user_b() -> None:
    with _api_client() as client:
        headers_a = _establish_session(client, oid="user-a")
        create_resp = client.post("/api/sessions", headers=headers_a)
        session_id = create_resp.json()["session_id"]

        headers_b = _establish_session(client, oid="user-b")

        # GET session
        resp = client.get(f"/api/sessions/{session_id}", headers=headers_b)
        assert resp.status_code == 403

        # SAS
        resp = client.post(f"/api/sessions/{session_id}/sas?filename=x.pdf", headers=headers_b)
        assert resp.status_code == 403

        # register file
        resp = client.post(
            f"/api/sessions/{session_id}/files",
            headers=headers_b,
            json={
                "filename": "x.pdf",
                "blob_path": f"{session_id}/x.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 100,
            },
        )
        assert resp.status_code == 403

        # confirm
        resp = client.post(f"/api/sessions/{session_id}/confirm", headers=headers_b)
        assert resp.status_code == 403


@pytest.mark.unit
def test_session_status_endpoint() -> None:
    with _api_client() as client:
        headers = _establish_session(client)
        create_resp = client.post("/api/sessions", headers=headers)
        session_id = create_resp.json()["session_id"]

        client.post(
            f"/api/sessions/{session_id}/files",
            headers=headers,
            json={
                "filename": "doc.pdf",
                "blob_path": f"{session_id}/doc.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 512,
            },
        )

        resp = client.get(f"/api/sessions/{session_id}/status", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == session_id
    assert body["total_files"] == 1
    assert "progress_percent" in body
    assert "files" in body


@pytest.mark.unit
def test_session_status_ownership() -> None:
    with _api_client() as client:
        headers_a = _establish_session(client, oid="owner-a")
        create_resp = client.post("/api/sessions", headers=headers_a)
        session_id = create_resp.json()["session_id"]

        headers_b = _establish_session(client, oid="owner-b")
        resp = client.get(f"/api/sessions/{session_id}/status", headers=headers_b)
    assert resp.status_code == 403
