from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class EscalationLevel(str, Enum):
    INITIAL = "initial"
    REMINDER_24H = "reminder_24h"
    ESCALATION_48H = "escalation_48h"
    FINAL_72H = "final_72h"
    EXPIRED = "expired"


class HITLNotification(BaseModel):
    albaran_id: str
    recipient_email: str
    subject: str
    body_html: str
    escalation_level: EscalationLevel
    callback_url: str
    pdf_sas_url: str
    expires_at: datetime


class HITLDecision(BaseModel):
    albaran_id: str
    decision: str
    modified_lines: list[dict[str, Any]] | None = None
    reviewer_email: str
    decided_at: datetime
    notes: str | None = None
