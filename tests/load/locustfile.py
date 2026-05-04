from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

from locust import HttpUser, between, task

TARGET_ALBARANES_PER_DAY = 750
SECONDS_PER_DAY = 24 * 60 * 60
TARGET_REQUESTS_PER_SECOND = TARGET_ALBARANES_PER_DAY / SECONDS_PER_DAY
DEFAULT_WAIT_SECONDS = max(1.0, round(1.0 / TARGET_REQUESTS_PER_SECOND, 2))

ORCHESTRATOR_HOST = os.getenv("VERDECORA_ORCHESTRATOR_HOST", "https://orchestrator.verdecora.example.com")
HITL_HOST = os.getenv("VERDECORA_HITL_HOST", "https://hitl-webform.verdecora.example.com")
BLOB_HOST = os.getenv("VERDECORA_BLOB_HOST", "https://storage.verdecora.example.com")
BLOB_CONTAINER = os.getenv("VERDECORA_BLOB_CONTAINER", "albaranes-raw")
BLOB_SAS_QUERY = os.getenv("VERDECORA_BLOB_SAS_QUERY", "")
HITL_AUTH_HEADER = os.getenv("VERDECORA_HITL_AUTH_HEADER", "Bearer signed.jwt")


class OrchestratorUser(HttpUser):
    host = ORCHESTRATOR_HOST
    wait_time = between(DEFAULT_WAIT_SECONDS, DEFAULT_WAIT_SECONDS * 1.5)

    @task(5)
    def process_albaran(self) -> None:
        request_id = uuid4().hex
        payload = {
            "blob_url": f"https://storageaccount.blob.core.windows.net/{BLOB_CONTAINER}/{request_id}.pdf",
            "metadata": {
                "supplier_id": "SUP-ROYAL-CANIN",
                "total_amount": 183.45,
                "captured_at": datetime.now(tz=UTC).isoformat(),
                "trace_id": request_id,
            },
        }
        self.client.post("/process", json=payload, name="POST /process")

    @task(1)
    def health(self) -> None:
        self.client.get("/health", name="GET /health")


class BlobUploadUser(HttpUser):
    host = BLOB_HOST
    wait_time = between(DEFAULT_WAIT_SECONDS, DEFAULT_WAIT_SECONDS * 1.25)

    @task(4)
    def upload_blob(self) -> None:
        document_id = uuid4().hex
        query = f"?{BLOB_SAS_QUERY.lstrip('?')}" if BLOB_SAS_QUERY else ""
        blob_path = f"/{BLOB_CONTAINER}/{datetime.now(tz=UTC):%Y/%m}/{document_id}.pdf{query}"
        self.client.put(
            blob_path,
            data=b"%PDF-1.4\n%Locust test document\n",
            headers={
                "x-ms-blob-type": "BlockBlob",
                "Content-Type": "application/pdf",
            },
            name="PUT blob upload",
        )


class HITLReviewerUser(HttpUser):
    host = HITL_HOST
    wait_time = between(DEFAULT_WAIT_SECONDS * 2, DEFAULT_WAIT_SECONDS * 4)

    @task(3)
    def open_review_page(self) -> None:
        self.client.get(
            "/review/alb-load-001",
            headers={"Authorization": HITL_AUTH_HEADER},
            name="GET /review/{id}",
        )

    @task(1)
    def submit_decision(self) -> None:
        self.client.post(
            "/review/alb-load-001/decide",
            headers={
                "Authorization": HITL_AUTH_HEADER,
                "Content-Type": "application/json",
            },
            json={
                "decision": "approve",
                "notes": "Carga de validación Locust.",
            },
            name="POST /review/{id}/decide",
        )

    @task(1)
    def health(self) -> None:
        self.client.get("/health", name="GET /health (HITL)")
