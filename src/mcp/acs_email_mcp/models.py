from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class EmailResult(BaseModel):
    message_id: str
    status: str
    recipients: list[str] = Field(default_factory=list)
    subject: str
    details: dict[str, Any] = Field(default_factory=dict)
    sent_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class DeliveryStatus(BaseModel):
    message_id: str
    status: str
    delivered: bool = False
    details: dict[str, Any] = Field(default_factory=dict)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
