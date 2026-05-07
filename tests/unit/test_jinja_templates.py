from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient

from src.upload_web.models.upload import UploadFile
from src.upload_web.app import create_app
from src.upload_web.services import upload_session


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


@pytest.fixture(autouse=True)
def _clear_upload_sessions() -> None:
    upload_session.clear_upload_sessions()
    yield
    upload_session.clear_upload_sessions()


@pytest.mark.unit
@pytest.mark.parametrize("path", ["/dashboard", "/upload", "/mis-albaranes"])
def test_templates_render_without_error(path: str) -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get(path, headers=_auth_headers())

    assert response.status_code == 200
    assert "Verdecora" in response.text
    assert "Cerrar sesión" in response.text


@pytest.mark.unit
def test_home_page_contains_expected_elements() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/dashboard", headers=_auth_headers("Parker Dev"))

    assert response.status_code == 200
    assert "Hola, Parker Dev" in response.text
    assert "Subir albarán" in response.text
    assert "Mis albaranes" in response.text
    assert 'href="/upload"' in response.text
    assert 'href="/mis-albaranes"' in response.text
    assert 'href="/logout"' in response.text
    assert "/static/css/tailwind.min.css" in response.text
    assert "/static/js/htmx.min.js" in response.text


@pytest.mark.unit
def test_public_landing_page_contains_login_cta() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Sistema de Gestión de Albaranes" in response.text
    assert "Iniciar sesión con Microsoft" in response.text
    assert "/.auth/login/aad?post_login_redirect_uri=%2Fdashboard" in response.text


@pytest.mark.unit
def test_upload_page_creates_session_and_binds_preflight_urls() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/upload", headers=_auth_headers("Parker Flow"))

    assert response.status_code == 200

    sessions = upload_session.get_all_user_sessions("oid-123")
    assert len(sessions) == 1
    session_id = sessions[0].session_id

    assert f'data-session-id="{session_id}"' in response.text
    assert 'href="/dashboard"' in response.text
    assert f'hx-post="/api/sessions/{session_id}/preflight"' in response.text
    assert 'id="preflight-loading"' in response.text


@pytest.mark.unit
def test_my_uploads_page_uses_relative_routes() -> None:
    app = create_app()

    with TestClient(app) as client:
        headers = _auth_headers("Parker Flow")
        client.get("/upload", headers=headers)

        sessions = upload_session.get_all_user_sessions("oid-123")
        assert len(sessions) == 1
        session = sessions[0]
        session_id = session.session_id
        session.files.append(
            UploadFile(
                file_id="file-1",
                filename="albaran.pdf",
                blob_path=f"{session_id}/albaran.pdf",
                content_type="application/pdf",
                size_bytes=1024,
            )
        )

        response = client.get("/mis-albaranes", headers=headers)

    assert response.status_code == 200
    assert 'href="/mis-albaranes"' in response.text
    assert 'hx-get="/mis-albaranes/filter?status_filter=created"' in response.text
    assert f"window.location='/upload/{session_id}/status'" in response.text
