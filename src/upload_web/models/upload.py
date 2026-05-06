from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class UploadFile(BaseModel):
    filename: str
    blob_path: str
    content_type: str
    size_bytes: int = Field(ge=0)
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


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
