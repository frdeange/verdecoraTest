from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field

from src.config.agents import DEFAULT_AZURE_AI_PROJECT_ENDPOINT


class LearningConfig(BaseModel):
    cosmos_endpoint: str = Field(default_factory=lambda: os.getenv("COSMOS_ENDPOINT", "https://localhost:8081"))
    database_name: str = Field(default_factory=lambda: os.getenv("DATABASE_NAME", "verdecora"))
    processing_container_name: str = Field(
        default_factory=lambda: os.getenv("PROCESSING_CONTAINER_NAME", "processing-records")
    )
    azure_ai_project_endpoint: str = Field(
        default_factory=lambda: os.getenv("AZURE_AI_PROJECT_ENDPOINT", DEFAULT_AZURE_AI_PROJECT_ENDPOINT)
    )
    analysis_window_days: int = Field(default_factory=lambda: int(os.getenv("LEARNING_WINDOW_DAYS", "7")))
    query_batch_size: int = Field(default_factory=lambda: int(os.getenv("LEARNING_BATCH_SIZE", "500")))
    apply_feature_flag_proposals: bool = Field(
        default_factory=lambda: (
            os.getenv("LEARNING_APPLY_FLAG_PROPOSALS", "false").strip().casefold() in {"1", "true", "yes", "on"}
        )
    )

    def create_credential(self) -> Any:
        try:
            from azure.identity import DefaultAzureCredential
        except ModuleNotFoundError as exc:  # pragma: no cover - optional runtime dependency.
            raise RuntimeError("azure-identity is required for the learning job.") from exc
        return DefaultAzureCredential(exclude_interactive_browser_credential=True)


@lru_cache(maxsize=1)
def get_learning_config() -> LearningConfig:
    return LearningConfig()
