from __future__ import annotations

import base64
import json
import re
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from src.upload_web.app import create_app
from src.upload_web.config import UploadWebSettings
from src.upload_web.middleware.session_security import (
    SESSION_COOKIE_NAME,
    SessionSecurityManager,
)

TEST_SIGNING_KEY = "test-session-signing-key-with-at-least-thirty-two-bytes"


def _settings() -> UploadWebSettings:
    return UploadWebSettings(session_signing_key=TEST_SIGNING_KEY)


def _build_client() -> TestClient:
    app = create_app(_settings())

    @app.post("/submit")
    async def submit() -> dict[str, str]:
        return {"status": "accepted"}

    @app.get("/test-form", response_class=HTMLResponse)
    async def test_form(request: Request) -> HTMLResponse:
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="base.html",
            context={
                "page_title": "Formulario de prueba",
                "hero_title": "Formulario de prueba",
                "hero_subtitle": "Prueba de CSRF.",
                "primary_action_href": "/submit",
                "primary_action_label": "Enviar",
            },
        )

    return TestClient(app, base_url="https://testserver")


def _auth_headers(expiry_offset_seconds: int = 3600) -> dict[str, str]:
    exp = int((datetime.now(UTC) + timedelta(seconds=expiry_offset_seconds)).timestamp())
    principal = {
        "auth_typ": "aad",
        "claims": [
            {
                "typ": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier",
                "val": "user-123",
            },
            {"typ": "name", "val": "Alice Upload"},
            {"typ": "preferred_username", "val": "alice.upload@verdecora.example"},
            {"typ": "groups", "val": "verdecora-store-uploaders"},
            {"typ": "exp", "val": str(exp)},
        ],
        "name_typ": "name",
        "role_typ": "roles",
    }
    encoded_principal = base64.b64encode(json.dumps(principal).encode("utf-8")).decode("utf-8")
    return {
        "X-MS-CLIENT-PRINCIPAL": encoded_principal,
        "X-MS-CLIENT-PRINCIPAL-ID": "user-123",
        "X-MS-CLIENT-PRINCIPAL-NAME": "Alice Upload",
        "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
    }


def _legacy_auth_headers(expiry_offset_seconds: int = 3600) -> dict[str, str]:
    exp = int((datetime.now(UTC) + timedelta(seconds=expiry_offset_seconds)).timestamp())
    token = jwt.encode(
        {"oid": "user-123", "name": "Alice Upload", "groups": ["verdecora-store-uploaders"], "exp": exp},
        "test-secret-with-at-least-thirty-two-bytes",
        algorithm="HS256",
    )
    return {"X-MS-TOKEN-AAD-ID-TOKEN": token}


def _extract_csrf_token(html: str) -> str:
    match = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    assert match is not None
    return match.group(1)


@pytest.mark.unit
def test_idle_timeout_redirects_to_logout() -> None:
    manager = SessionSecurityManager(_settings())

    with _build_client() as client:
        initial_response = client.get("/", headers=_auth_headers())
        cookie_value = client.cookies.get(SESSION_COOKIE_NAME)
        assert initial_response.status_code == 200
        assert cookie_value is not None

        stale_payload = manager.loads(cookie_value)
        stale_payload["last_activity"] = int((datetime.now(UTC) - timedelta(minutes=31)).timestamp())
        client.cookies.set(SESSION_COOKIE_NAME, manager.dumps(stale_payload))

        response = client.get("/uploads", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/logout?reason=idle"


@pytest.mark.unit
def test_csrf_token_generation_and_validation() -> None:
    with _build_client() as client:
        response = client.get("/test-form", headers=_auth_headers())
        csrf_token = _extract_csrf_token(response.text)

        assert response.status_code == 200
        assert csrf_token
        assert f'content="{csrf_token}"' in response.text
        assert SESSION_COOKIE_NAME in response.headers["set-cookie"]
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=lax" in response.headers["set-cookie"]
        assert "Secure" in response.headers["set-cookie"]
        assert "Max-Age=28800" in response.headers["set-cookie"]
        assert "Path=/" in response.headers["set-cookie"]

        accepted = client.post("/submit", headers={"X-CSRF-Token": csrf_token})
        rejected = client.post("/submit", headers={"X-CSRF-Token": "wrong-token"})

    assert accepted.status_code == 200
    assert accepted.json() == {"status": "accepted"}
    assert rejected.status_code == 403
    assert rejected.json() == {"detail": "CSRF token validation failed."}


@pytest.mark.unit
def test_security_headers_are_set() -> None:
    with _build_client() as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Content-Security-Policy"] == (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self' https://login.microsoftonline.com"
    )


@pytest.mark.unit
def test_logout_clears_session_cookie() -> None:
    with _build_client() as client:
        client.get("/", headers=_auth_headers())

        response = client.get("/logout", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/.auth/logout?post_logout_redirect_uri=%2F"
    assert f"{SESSION_COOKIE_NAME}=\"\"" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert "Secure" in response.headers["set-cookie"]


@pytest.mark.unit
def test_direct_client_principal_headers_allow_authentication() -> None:
    app = create_app(_settings())

    with TestClient(app, base_url="https://testserver") as client:
        response = client.get(
            "/dashboard",
            headers={
                "X-MS-CLIENT-PRINCIPAL-ID": "direct-user-123",
                "X-MS-CLIENT-PRINCIPAL-NAME": "Direct User",
                "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
            },
        )

    assert response.status_code == 200
    assert "Hola, Direct User" in response.text


@pytest.mark.unit
def test_legacy_id_token_remains_supported() -> None:
    with _build_client() as client:
        response = client.get("/dashboard", headers=_legacy_auth_headers())

    assert response.status_code == 200
    assert "Hola, Alice Upload" in response.text
