from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field


def _get_env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _get_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().casefold() in {"1", "true", "yes", "on"}


class OrchestratorConfig(BaseModel):
    service_bus_namespace: str = Field(default_factory=lambda: _get_env("SERVICE_BUS_NAMESPACE", "verdecora-dev"))
    extraction_queue_name: str = Field(default_factory=lambda: _get_env("EXTRACTION_QUEUE_NAME", "extraction"))
    hitl_queue_name: str = Field(default_factory=lambda: _get_env("HITL_QUEUE_NAME", "hitl-review"))
    cosmos_endpoint: str = Field(default_factory=lambda: _get_env("COSMOS_ENDPOINT", "https://localhost:8081"))
    database_name: str = Field(default_factory=lambda: _get_env("DATABASE_NAME", "verdecora"))
    processing_container_name: str = Field(
        default_factory=lambda: _get_env("PROCESSING_CONTAINER_NAME", "processing-records")
    )
    storage_account_url: str = Field(
        default_factory=lambda: _get_env("STORAGE_ACCOUNT_URL", "https://examplestorage.blob.core.windows.net")
    )
    azure_openai_endpoint: str = Field(
        default_factory=lambda: _get_env("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    )
    azure_openai_api_version: str = Field(default_factory=lambda: _get_env("AZURE_OPENAI_API_VERSION", "2024-10-21"))
    docintell_endpoint: str = Field(
        default_factory=lambda: _get_env("DOCINTELL_ENDPOINT", "https://example.cognitiveservices.azure.com/")
    )
    service_bus_polling_enabled: bool = Field(
        default_factory=lambda: _get_bool_env("SERVICE_BUS_POLLING_ENABLED", True)
    )
    service_bus_poll_interval_seconds: float = Field(
        default_factory=lambda: float(_get_env("SERVICE_BUS_POLL_INTERVAL_SECONDS", "5"))
    )
    max_receive_batch_size: int = Field(default_factory=lambda: int(_get_env("SERVICE_BUS_BATCH_SIZE", "5")))
    max_delivery_attempts: int = Field(default_factory=lambda: int(_get_env("MAX_DELIVERY_ATTEMPTS", "5")))

    @property
    def service_bus_fully_qualified_namespace(self) -> str:
        if "." in self.service_bus_namespace:
            return self.service_bus_namespace
        return f"{self.service_bus_namespace}.servicebus.windows.net"

    def create_credential(self) -> Any:
        try:
            from azure.identity import DefaultAzureCredential
        except ModuleNotFoundError as exc:  # pragma: no cover - optional in local unit-test environments.
            raise RuntimeError(
                "azure-identity is required to create Managed Identity credentials for the orchestrator."
            ) from exc

        return DefaultAzureCredential(exclude_interactive_browser_credential=True)


@lru_cache(maxsize=1)
def get_orchestrator_config() -> OrchestratorConfig:
    return OrchestratorConfig()
