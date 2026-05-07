from __future__ import annotations

import httpx
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]


async def test_healthz_returns_200(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_returns_200(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_home_shows_public_landing(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get("/", follow_redirects=False)

    assert response.status_code == 200
    assert "Sistema de Gestión de Albaranes" in response.text


async def test_api_sessions_requires_auth(app_client: httpx.AsyncClient) -> None:
    response = await app_client.post("/api/sessions")

    assert response.status_code == 401


async def test_upload_page_requires_auth(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get("/uploads", follow_redirects=False)

    assert response.status_code in {302, 401}


async def test_home_redirects_authenticated_user_to_dashboard(
    app_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await app_client.get("/", headers=auth_headers, follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/dashboard"


async def test_dashboard_renders_for_authenticated_user(
    app_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await app_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    assert "Vasquez QA" in response.text


async def test_mis_albaranes_renders(app_client: httpx.AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await app_client.get("/mis-albaranes", headers=auth_headers)

    assert response.status_code == 200
    assert "Mis albaranes" in response.text


async def test_verdecora_css_accessible(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get("/static/css/verdecora.css")

    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]


async def test_logo_accessible(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get("/static/img/verdecora-logo.jpg")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
