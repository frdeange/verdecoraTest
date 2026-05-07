"""Locust load test for Upload Web — 30 RPS / 30 min (#120).

Simulates 30 concurrent store users performing the full upload flow:
create session → upload 3 files → preflight → confirm.

All endpoints target the Upload Web API routes; no real Azure calls are
made (set ``UPLOAD_WEB_HOST`` to a local/mock server).

Run:
    locust -f tests/load/upload_web_locustfile.py --headless \
           -u 30 -r 5 --run-time 30m \
           --host http://localhost:8000
"""

from __future__ import annotations

import base64
import json
import os
from uuid import uuid4

from locust import HttpUser, between, task

UPLOAD_WEB_HOST = os.getenv("UPLOAD_WEB_HOST", "http://localhost:8000")
AUTH_TOKEN = os.getenv("UPLOAD_WEB_AUTH_TOKEN", "Bearer test.jwt.token")
CLIENT_PRINCIPAL = os.getenv(
    "UPLOAD_WEB_CLIENT_PRINCIPAL",
    base64.b64encode(
        json.dumps(
            {
                "auth_typ": "aad",
                "claims": [
                    {
                        "typ": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier",
                        "val": "load-test-user",
                    },
                    {"typ": "name", "val": "Load Test User"},
                    {"typ": "preferred_username", "val": "load.test@verdecora.example"},
                    {"typ": "groups", "val": "verdecora-store-uploaders"},
                ],
                "name_typ": "name",
                "role_typ": "roles",
            }
        ).encode("utf-8")
    ).decode("utf-8"),
)
CSRF_TOKEN = os.getenv("UPLOAD_WEB_CSRF_TOKEN", "test-csrf-token")

COMMON_HEADERS = {
    "Authorization": AUTH_TOKEN,
    "X-MS-CLIENT-PRINCIPAL": CLIENT_PRINCIPAL,
    "X-MS-CLIENT-PRINCIPAL-ID": os.getenv("UPLOAD_WEB_CLIENT_PRINCIPAL_ID", "load-test-user"),
    "X-MS-CLIENT-PRINCIPAL-NAME": os.getenv("UPLOAD_WEB_CLIENT_PRINCIPAL_NAME", "Load Test User"),
    "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
    "X-CSRF-Token": CSRF_TOKEN,
}


class UploadWebUser(HttpUser):
    """Simulates a store staff member uploading a delivery note."""

    host = UPLOAD_WEB_HOST
    wait_time = between(0.5, 1.5)

    @task
    def full_upload_flow(self) -> None:
        # 1. Create session
        with self.client.post(
            "/api/sessions",
            headers=COMMON_HEADERS,
            name="POST /api/sessions",
            catch_response=True,
        ) as resp:
            if resp.status_code != 201:
                resp.failure(f"Session creation failed: {resp.status_code}")
                return
            session_id = resp.json().get("session_id", uuid4().hex)

        # 2. Upload 3 files (SAS generation + file registration)
        for i in range(3):
            filename = f"albaran-test-{uuid4().hex[:8]}-{i}.pdf"

            self.client.post(
                f"/api/sessions/{session_id}/sas?filename={filename}",
                headers=COMMON_HEADERS,
                name="POST /api/sessions/{id}/sas",
            )

            self.client.post(
                f"/api/sessions/{session_id}/files",
                headers=COMMON_HEADERS,
                json={
                    "filename": filename,
                    "blob_path": f"uploads/{session_id}/{filename}",
                    "mime_type": "application/pdf",
                    "size_bytes": 204800,
                },
                name="POST /api/sessions/{id}/files",
            )

        # 3. Preflight
        self.client.post(
            f"/api/sessions/{session_id}/preflight",
            headers=COMMON_HEADERS,
            name="POST /api/sessions/{id}/preflight",
        )

        # 4. Confirm
        self.client.post(
            f"/api/sessions/{session_id}/confirm",
            headers=COMMON_HEADERS,
            name="POST /api/sessions/{id}/confirm",
        )

    @task(1)
    def healthz(self) -> None:
        self.client.get("/healthz", name="GET /healthz")
