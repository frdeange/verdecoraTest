from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field


class AzureServiceEndpoints(BaseModel):
    azure_openai_endpoint: str = Field(
        default_factory=lambda: os.getenv(
            "AZURE_OPENAI_ENDPOINT",
            "https://verdecora-openai-dev.openai.azure.com/",
        )
    )
    document_intelligence_endpoint: str = Field(
        default_factory=lambda: os.getenv(
            "DOCUMENT_INTELLIGENCE_ENDPOINT",
            "https://verdecora-docintell-dev.cognitiveservices.azure.com/",
        )
    )
    azure_openai_api_version: str = Field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"))


class AgentModelSettings(BaseModel):
    extractor_model: str = Field(default_factory=lambda: os.getenv("GPT5_DEPLOYMENT", "gpt-5"))
    triage_model: str = Field(default_factory=lambda: os.getenv("GPT5_MINI_DEPLOYMENT", "gpt-5-mini"))
    coherence_model: str = Field(default_factory=lambda: os.getenv("GPT5_MINI_DEPLOYMENT", "gpt-5-mini"))


class AgentThresholdSettings(BaseModel):
    triage_manual_review_threshold: float = Field(
        default_factory=lambda: float(os.getenv("TRIAGE_MANUAL_REVIEW_THRESHOLD", "0.65"))
    )
    low_value_coherence_threshold: float = Field(
        default_factory=lambda: float(os.getenv("LOW_VALUE_COHERENCE_THRESHOLD", "250.0"))
    )


class AgentsConfig(BaseModel):
    endpoints: AzureServiceEndpoints = Field(default_factory=AzureServiceEndpoints)
    models: AgentModelSettings = Field(default_factory=AgentModelSettings)
    thresholds: AgentThresholdSettings = Field(default_factory=AgentThresholdSettings)
    skip_triage_suppliers: tuple[str, ...] = Field(
        default_factory=lambda: tuple(
            supplier.strip() for supplier in os.getenv("SKIP_TRIAGE_SUPPLIERS", "").split(",") if supplier.strip()
        )
    )

    def create_credential(self) -> Any:
        try:
            from azure.identity import DefaultAzureCredential
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional Azure SDK.
            raise RuntimeError(
                "azure-identity is required to create Managed Identity credentials for agent clients."
            ) from exc

        return DefaultAzureCredential(exclude_interactive_browser_credential=True)


@lru_cache(maxsize=1)
def get_agents_config() -> AgentsConfig:
    return AgentsConfig()
