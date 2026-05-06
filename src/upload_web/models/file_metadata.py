from __future__ import annotations

from pydantic import BaseModel, Field


class FileMetadata(BaseModel):
    """Metadata sent by the frontend after a successful SAS upload."""

    filename: str = Field(min_length=1, max_length=255)
    blob_path: str = Field(min_length=1)
    mime_type: str
    size_bytes: int = Field(ge=0)
    albaran_group: str | None = None
    page_number: int = 1
