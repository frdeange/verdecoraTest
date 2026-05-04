from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field

from src.config.agents import DEFAULT_AZURE_AI_PROJECT_ENDPOINT


class ReconciliationConfig(BaseModel):
    cosmos_endpoint: str = Field(default_factory=lambda: os.getenv("COSMOS_ENDPOINT", "https://localhost:8081"))
    database_name: str = Field(default_factory=lambda: os.getenv("DATABASE_NAME", "verdecora"))
    processing_container_name: str = Field(
        default_factory=lambda: os.getenv("PROCESSING_CONTAINER_NAME", "processing-records")
    )
    azure_ai_project_endpoint: str = Field(
        default_factory=lambda: os.getenv("AZURE_AI_PROJECT_ENDPOINT", DEFAULT_AZURE_AI_PROJECT_ENDPOINT)
    )
    service_bus_namespace: str = Field(default_factory=lambda: os.getenv("SERVICE_BUS_NAMESPACE", "verdecora-dev"))
    acs_endpoint: str = Field(
        default_factory=lambda: os.getenv("ACS_ENDPOINT", "https://example.unitedstates.communication.azure.com")
    )
    reconciliation_window_hours: int = Field(
        default_factory=lambda: int(os.getenv("RECONCILIATION_WINDOW_HOURS", "24"))
    )
    query_batch_size: int = Field(default_factory=lambda: int(os.getenv("RECONCILIATION_BATCH_SIZE", "200")))
    amount_tolerance: float = Field(default_factory=lambda: float(os.getenv("RECONCILIATION_AMOUNT_TOLERANCE", "0.01")))
    report_recipients: tuple[str, ...] = Field(
        default_factory=lambda: tuple(
            item.strip() for item in os.getenv("RECONCILIATION_REPORT_RECIPIENTS", "").split(",") if item.strip()
        )
    )
    auto_fix_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("RECONCILIATION_AUTO_FIX_ENABLED", "false").strip().casefold() in {"1", "true", "yes", "on"}
        )
    )

    def create_credential(self) -> Any:
        try:
            from azure.identity import DefaultAzureCredential
        except ModuleNotFoundError as exc:  # pragma: no cover - optional runtime dependency.
            raise RuntimeError("azure-identity is required for the reconciliation job.") from exc
        return DefaultAzureCredential(exclude_interactive_browser_credential=True)


@lru_cache(maxsize=1)
def get_reconciliation_config() -> ReconciliationConfig:
    return ReconciliationConfig()
