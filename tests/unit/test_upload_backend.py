"""Tests for blob_sas, file_validator, preflight, and new API endpoints."""

from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient
from itsdangerous import URLSafeSerializer

from src.upload_web.app import create_app
from src.upload_web.config import get_settings
from src.upload_web.models.file_metadata import FileMetadata
from src.upload_web.models.upload import SessionStatus, UploadFile, UploadSession
from src.upload_web.services import upload_session
from src.upload_web.services.blob_sas import generate_upload_sas_url
from src.upload_web.services.file_validator import (
    sanitize_filename,
    validate_file,
    validate_file_size,
    validate_mime_type,
    validate_session_size,
)
from src.upload_web.services.preflight import run_preflight

SIGNING_KEY = "dev-only-upload-web-session-signing-key-change-me"


def _auth_headers(oid: str = "oid-123", name: str = "Parker Store") -> dict[str, str]:
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


def _establish_session(client: TestClient, oid: str = "oid-123", name: str = "Parker Store") -> dict[str, str]:
    """Make a GET to establish a session cookie and extract the CSRF token for POST requests."""
    headers = _auth_headers(oid, name)
    client.get("/", headers=headers)
    cookie_value = client.cookies.get("upload_web_session", "")
    if cookie_value:
        serializer = URLSafeSerializer(SIGNING_KEY, salt="upload-web-session")
        payload = serializer.loads(cookie_value)
        headers["X-CSRF-Token"] = payload.get("csrf_token", "")
    return headers


@pytest.fixture(autouse=True)
def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STORAGE_ACCOUNT_URL", raising=False)
    monkeypatch.delenv("BLOB_ACCOUNT", raising=False)
    upload_session.clear_upload_sessions()
    yield
    upload_session.clear_upload_sessions()
    get_settings.cache_clear()


# ── SessionStatus enum ──────────────────────────────────────────────


@pytest.mark.unit
def test_session_status_values() -> None:
    assert SessionStatus.DRAFT == "draft"
    assert SessionStatus.CONFIRMED == "confirmed"
    assert SessionStatus.CREATED == "created"


# ── FileMetadata model ──────────────────────────────────────────────


@pytest.mark.unit
def test_file_metadata_defaults() -> None:
    fm = FileMetadata(filename="test.pdf", blob_path="s/test.pdf", mime_type="application/pdf", size_bytes=1024)
    assert fm.page_number == 1
    assert fm.albaran_group is None


# ── file_validator ───────────────────────────────────────────────────


@pytest.mark.unit
def test_validate_mime_type_accepts_pdf() -> None:
    assert validate_mime_type("application/pdf") == []


@pytest.mark.unit
def test_validate_mime_type_rejects_zip() -> None:
    errors = validate_mime_type("application/zip")
    assert len(errors) == 1
    assert "not allowed" in errors[0]


@pytest.mark.unit
def test_validate_file_size_ok() -> None:
    assert validate_file_size(10 * 1024 * 1024) == []


@pytest.mark.unit
def test_validate_file_size_too_large() -> None:
    errors = validate_file_size(60 * 1024 * 1024)
    assert len(errors) == 1
    assert "50 MB" in errors[0]


@pytest.mark.unit
def test_validate_session_size_ok() -> None:
    assert validate_session_size(100 * 1024 * 1024, 50 * 1024 * 1024) == []


@pytest.mark.unit
def test_validate_session_size_exceeds() -> None:
    errors = validate_session_size(180 * 1024 * 1024, 30 * 1024 * 1024)
    assert len(errors) == 1
    assert "200 MB" in errors[0]


@pytest.mark.unit
def test_sanitize_filename_strips_path() -> None:
    safe, errors = sanitize_filename("../../etc/passwd")
    assert "path traversal" in errors[0].lower()


@pytest.mark.unit
def test_sanitize_filename_valid() -> None:
    safe, errors = sanitize_filename("albaran_001.pdf")
    assert safe == "albaran_001.pdf"
    assert errors == []


@pytest.mark.unit
def test_validate_file_all_good() -> None:
    result = validate_file("test.pdf", "application/pdf", 1024)
    assert result.valid is True
    assert result.errors == []


@pytest.mark.unit
def test_validate_file_bad_mime_and_size() -> None:
    result = validate_file("test.exe", "application/x-executable", 60 * 1024 * 1024)
    assert result.valid is False
    assert len(result.errors) >= 2


# ── blob_sas (mock mode) ────────────────────────────────────────────


@pytest.mark.unit
def test_generate_upload_sas_url_returns_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STORAGE_ACCOUNT_URL", raising=False)
    monkeypatch.delenv("BLOB_ACCOUNT", raising=False)
    get_settings.cache_clear()

    sas_url, blob_path, expires_in = generate_upload_sas_url("session-abc", "file.pdf")

    assert "mock" in sas_url
    assert blob_path == "session-abc/file.pdf"
    assert expires_in == 900


# ── preflight (heuristic mode) ──────────────────────────────────────


@pytest.mark.unit
def test_preflight_no_files() -> None:
    session = UploadSession(session_id="s1", user_oid="u1", user_name="Test")
    result = run_preflight(session)
    assert result.files_analyzed == 0
    assert result.confidence <= 0.1


@pytest.mark.unit
def test_preflight_with_text() -> None:
    session = UploadSession(
        session_id="s1",
        user_oid="u1",
        user_name="Test",
        files=[UploadFile(filename="p1.pdf", blob_path="s1/p1.pdf", content_type="application/pdf", size_bytes=100)],
    )
    doc_results = [{"content": "ALBARÁN Nº: ALB-2024-001\nFecha: 15/03/2024\nProveedor: Plantas Sur S.L."}]
    result = run_preflight(session, doc_results)

    assert result.is_albaran is True
    assert result.detected_albaran_number is not None
    assert result.detected_date == "15/03/2024"
    assert result.confidence > 0.0


# ── API endpoint tests (use HTTPS base_url for secure cookies) ──────


def _api_client() -> TestClient:
    """Create a TestClient with HTTPS base URL so secure cookies are sent."""
    return TestClient(create_app(), base_url="https://testserver")


@pytest.mark.unit
def test_api_sas_endpoint() -> None:
    with _api_client() as client:
        headers = _establish_session(client)
        create_resp = client.post("/api/sessions", headers=headers)
        assert create_resp.status_code == 201
        session_id = create_resp.json()["session_id"]

        sas_resp = client.post(f"/api/sessions/{session_id}/sas?filename=test.pdf", headers=headers)

    assert sas_resp.status_code == 200
    body = sas_resp.json()
    assert "upload_url" in body
    assert body["blob_path"] == f"{session_id}/test.pdf"
    assert body["expires_in"] == 900


@pytest.mark.unit
def test_api_sas_wrong_user() -> None:
    with _api_client() as client:
        headers_a = _establish_session(client, oid="user-a")
        create_resp = client.post("/api/sessions", headers=headers_a)
        session_id = create_resp.json()["session_id"]

        headers_b = _establish_session(client, oid="user-b")
        sas_resp = client.post(f"/api/sessions/{session_id}/sas?filename=test.pdf", headers=headers_b)

    assert sas_resp.status_code == 403


@pytest.mark.unit
def test_api_register_file() -> None:
    with _api_client() as client:
        headers = _establish_session(client)
        create_resp = client.post("/api/sessions", headers=headers)
        session_id = create_resp.json()["session_id"]

        reg_resp = client.post(
            f"/api/sessions/{session_id}/files",
            headers=headers,
            json={
                "filename": "albaran.pdf",
                "blob_path": f"{session_id}/albaran.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 2048,
            },
        )

    assert reg_resp.status_code == 201
    body = reg_resp.json()
    assert body["status"] == "registered"
    assert "file_id" in body


@pytest.mark.unit
def test_api_register_file_bad_mime() -> None:
    with _api_client() as client:
        headers = _establish_session(client)
        create_resp = client.post("/api/sessions", headers=headers)
        session_id = create_resp.json()["session_id"]

        reg_resp = client.post(
            f"/api/sessions/{session_id}/files",
            headers=headers,
            json={
                "filename": "malware.exe",
                "blob_path": f"{session_id}/malware.exe",
                "mime_type": "application/x-executable",
                "size_bytes": 2048,
            },
        )

    assert reg_resp.status_code == 422


@pytest.mark.unit
def test_api_preflight_no_files() -> None:
    with _api_client() as client:
        headers = _establish_session(client)
        create_resp = client.post("/api/sessions", headers=headers)
        session_id = create_resp.json()["session_id"]

        pf_resp = client.post(f"/api/sessions/{session_id}/preflight", headers=headers)

    assert pf_resp.status_code == 400


@pytest.mark.unit
def test_api_preflight_with_files() -> None:
    with _api_client() as client:
        headers = _establish_session(client)
        create_resp = client.post("/api/sessions", headers=headers)
        session_id = create_resp.json()["session_id"]

        client.post(
            f"/api/sessions/{session_id}/files",
            headers=headers,
            json={
                "filename": "page1.pdf",
                "blob_path": f"{session_id}/page1.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )

        pf_resp = client.post(f"/api/sessions/{session_id}/preflight", headers=headers)

    assert pf_resp.status_code == 200
    body = pf_resp.json()
    assert body["session_id"] == session_id
    assert "confidence" in body


@pytest.mark.unit
def test_api_confirm_session() -> None:
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

        confirm_resp = client.post(f"/api/sessions/{session_id}/confirm", headers=headers)

    assert confirm_resp.status_code == 200
    body = confirm_resp.json()
    assert body["status"] == "confirmed"


@pytest.mark.unit
def test_api_confirm_no_files() -> None:
    with _api_client() as client:
        headers = _establish_session(client)
        create_resp = client.post("/api/sessions", headers=headers)
        session_id = create_resp.json()["session_id"]

        confirm_resp = client.post(f"/api/sessions/{session_id}/confirm", headers=headers)

    assert confirm_resp.status_code == 400


@pytest.mark.unit
def test_api_confirm_idempotent() -> None:
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

        client.post(f"/api/sessions/{session_id}/confirm", headers=headers)
        second_resp = client.post(f"/api/sessions/{session_id}/confirm", headers=headers)

    assert second_resp.status_code == 200
    assert second_resp.json()["processing_started"] is False


# ── HTML page endpoints ──────────────────────────────────────────────


@pytest.mark.unit
def test_confirm_store_page_404() -> None:
    with _api_client() as client:
        resp = client.get("/upload/nonexistent/confirm-store", headers=_auth_headers())
    assert resp.status_code == 404


@pytest.mark.unit
def test_summary_page_404() -> None:
    with _api_client() as client:
        resp = client.get("/upload/nonexistent/summary", headers=_auth_headers())
    assert resp.status_code == 404


@pytest.mark.unit
def test_confirm_store_page_renders() -> None:
    with _api_client() as client:
        headers = _establish_session(client)
        create_resp = client.post("/api/sessions", headers=headers)
        session_id = create_resp.json()["session_id"]

        resp = client.get(f"/upload/{session_id}/confirm-store", headers=_auth_headers())

    assert resp.status_code == 200
    assert "Confirmar tienda" in resp.text


@pytest.mark.unit
def test_summary_page_renders() -> None:
    with _api_client() as client:
        headers = _establish_session(client)
        create_resp = client.post("/api/sessions", headers=headers)
        session_id = create_resp.json()["session_id"]

        resp = client.get(f"/upload/{session_id}/summary", headers=_auth_headers())

    assert resp.status_code == 200
    assert "Resumen" in resp.text
