from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field


class BlobCreatedData(BaseModel):
    """Subset of the Event Grid storage payload used by Flow 0."""

    model_config = ConfigDict(extra="allow")

    api: str | None = None
    clientRequestId: str | None = None
    requestId: str | None = None
    eTag: str | None = None
    contentType: str | None = None
    contentLength: int | None = None
    url: str | None = None
    blobType: str | None = None
    sequencer: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    storageDiagnostics: dict[str, Any] = Field(default_factory=dict)

    @property
    def blob_hash(self) -> str | None:
        """Return the best available blob hash-like fingerprint."""

        for key in ("blob_hash", "blobHash", "content_md5", "contentMd5"):
            value = self.metadata.get(key)
            if value:
                return value
        return None


class EventGridEnvelope(BaseModel):
    """Typed representation of the Event Grid BlobCreated envelope."""

    model_config = ConfigDict(extra="allow")

    id: str
    eventType: str
    subject: str
    eventTime: datetime
    data: BlobCreatedData
    topic: str | None = None
    dataVersion: str | None = None
    metadataVersion: str | None = None

    @property
    def blob_url(self) -> str:
        """Return the storage URL associated with the event."""

        if not self.data.url:
            raise ValueError("BlobCreated event does not include data.url")
        return self.data.url

    @property
    def blob_path(self) -> str:
        """Return the storage path without the leading slash."""

        return urlparse(self.blob_url).path.lstrip("/")

    @property
    def blob_name(self) -> str:
        """Return the final path segment for the blob."""

        return self.blob_path.rsplit("/", maxsplit=1)[-1]


class ProcessingRecord(BaseModel):
    """Cosmos DB document created by Flow 0 before the orchestrator picks up work."""

    model_config = ConfigDict(extra="forbid")

    id: str
    pk: str
    status: str = "pending"
    estado: str = "pending"
    store_id: str
    event_id: str
    event_type: str
    event_time: datetime
    event_date: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    dedup_key: str
    blob_url: str
    blob_path: str
    blob_name: str
    blob_etag: str | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    upload_session_id: str | None = None
    uploader_oid: str | None = None


class ForwardedExtractionMessage(BaseModel):
    """Message forwarded by Flow 0 into the extraction queue."""

    model_config = ConfigDict(extra="forbid")

    albaran_id: str
    dedup_key: str
    status: str = "pending"
    blob_url: str
    blob_path: str
    blob_name: str
    blob_etag: str | None = None
    store_id: str
    event_id: str
    event_time: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    upload_session_id: str | None = None
    uploader_oid: str | None = None
    albaran_group: str | None = None
