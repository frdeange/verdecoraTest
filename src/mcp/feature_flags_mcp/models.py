from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FlagOverride(BaseModel):
    """A contextual override for a feature flag."""

    model_config = ConfigDict(extra="forbid")

    match: dict[str, Any] = Field(default_factory=dict)
    value: Any = None


class FlagValue(BaseModel):
    """A feature flag value stored in Cosmos DB."""

    model_config = ConfigDict(extra="forbid")

    flag_name: str
    value: Any = None
    description: str | None = None
    version: int = 1
    overrides: list[FlagOverride] = Field(default_factory=list)
    updated_at: str | None = None


class SupplierConfig(BaseModel):
    """Per-supplier triage or behavior overrides."""

    model_config = ConfigDict(extra="forbid")

    supplier_id: str
    configuration: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None
    updated_at: str | None = None
