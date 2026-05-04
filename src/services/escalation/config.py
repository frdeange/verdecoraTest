from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field


class EscalationConfig(BaseModel):
    reminder_after_hours: int = Field(default_factory=lambda: int(os.getenv("HITL_REMINDER_AFTER_HOURS", "24")))
    escalation_after_hours: int = Field(default_factory=lambda: int(os.getenv("HITL_ESCALATION_AFTER_HOURS", "48")))
    final_after_hours: int = Field(default_factory=lambda: int(os.getenv("HITL_FINAL_AFTER_HOURS", "72")))
    cosmos_endpoint: str = Field(default_factory=lambda: os.getenv("COSMOS_ENDPOINT", "https://localhost:8081"))
    database_name: str = Field(default_factory=lambda: os.getenv("DATABASE_NAME", "verdecora"))
    processing_container_name: str = Field(
        default_factory=lambda: os.getenv("PROCESSING_CONTAINER_NAME", "processing-records")
    )
    query_batch_size: int = Field(default_factory=lambda: int(os.getenv("HITL_ESCALATION_BATCH_SIZE", "100")))

    def create_credential(self) -> Any:
        try:
            from azure.identity import DefaultAzureCredential
        except ModuleNotFoundError as exc:  # pragma: no cover - optional runtime dependency.
            raise RuntimeError("azure-identity is required for the escalation job.") from exc
        return DefaultAzureCredential(exclude_interactive_browser_credential=True)


@lru_cache(maxsize=1)
def get_escalation_config() -> EscalationConfig:
    return EscalationConfig()
