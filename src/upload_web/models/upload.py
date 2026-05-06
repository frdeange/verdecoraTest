from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SessionStatus(StrEnum):
    DRAFT = "draft"
    UPLOADING = "uploading"
    PREFLIGHT = "preflight"
    CONFIRMING = "confirming"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CREATED = "created"


class UploadFile(BaseModel):
    file_id: str = ""
    filename: str
    blob_path: str
    content_type: str
    size_bytes: int = Field(ge=0)
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    albaran_group: str | None = None
    page_number: int = 1


class PreflightSummary(BaseModel):
    """Lightweight preflight results stored inside the session."""

    detected_supplier: str | None = None
    detected_date: str | None = None
    detected_albaran_number: str | None = None
    detected_store: str | None = None
    confidence: float = 0.0
    is_albaran: bool = False
    warnings: list[str] = Field(default_factory=list)


class UploadSession(BaseModel):
    session_id: str
    user_oid: str
    user_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str = "created"
    files: list[UploadFile] = Field(default_factory=list)
    container_name: str = "albaranes-raw"
    upload_prefix: str = ""
    sas_token: str = ""
    sas_expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    preflight: PreflightSummary | None = None
    confirmed_store: str | None = None
    confirmed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
