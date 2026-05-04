from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field


class HITLWebformConfig(BaseModel):
    cosmos_endpoint: str = Field(default_factory=lambda: os.getenv("COSMOS_ENDPOINT", "https://localhost:8081"))
    database_name: str = Field(default_factory=lambda: os.getenv("DATABASE_NAME", "verdecora"))
    processing_container_name: str = Field(
        default_factory=lambda: os.getenv("PROCESSING_CONTAINER_NAME", "processing-records")
    )
    service_bus_namespace: str = Field(default_factory=lambda: os.getenv("SERVICE_BUS_NAMESPACE", "verdecora-dev"))
    hitl_decisions_topic_name: str = Field(
        default_factory=lambda: os.getenv("HITL_DECISIONS_TOPIC_NAME", "hitl-decisions")
    )
    public_base_url: str = Field(
        default_factory=lambda: os.getenv("HITL_WEBFORM_BASE_URL", "https://hitl-webform.example.com")
    )
    expected_audience: str = Field(default_factory=lambda: os.getenv("HITL_EXPECTED_AUDIENCE", "api://verdecora-hitl"))

    @property
    def service_bus_fully_qualified_namespace(self) -> str:
        if "." in self.service_bus_namespace:
            return self.service_bus_namespace
        return f"{self.service_bus_namespace}.servicebus.windows.net"

    def create_credential(self) -> Any:
        try:
            from azure.identity import DefaultAzureCredential
        except ModuleNotFoundError as exc:  # pragma: no cover - optional runtime dependency.
            raise RuntimeError("azure-identity is required for the HITL webform service.") from exc
        return DefaultAzureCredential(exclude_interactive_browser_credential=True)


@lru_cache(maxsize=1)
def get_hitl_webform_config() -> HITLWebformConfig:
    return HITLWebformConfig()
