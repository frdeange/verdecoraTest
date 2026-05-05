from __future__ import annotations

import jwt
import pytest
from fastapi.testclient import TestClient

from src.upload_web.app import create_app

TEST_SECRET = "test-secret-with-at-least-thirty-two-bytes"


def _auth_headers(name: str = "Parker Store") -> dict[str, str]:
    token = jwt.encode(
        {
            "oid": "oid-123",
            "name": name,
            "groups": ["verdecora-store-uploaders"],
            "exp": 9999999999,
        },
        TEST_SECRET,
        algorithm="HS256",
    )
    return {"X-MS-TOKEN-AAD-ID-TOKEN": token}


@pytest.mark.unit
@pytest.mark.parametrize("path", ["/", "/upload", "/mis-albaranes"])
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
        response = client.get("/", headers=_auth_headers("Parker Dev"))

    assert response.status_code == 200
    assert "Hola, Parker Dev" in response.text
    assert "Subir albarán" in response.text
    assert "Mis albaranes" in response.text
    assert "tailwindcss.com" in response.text
    assert "htmx.org" in response.text
