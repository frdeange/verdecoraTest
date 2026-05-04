from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CosmosQueryParameter(BaseModel):
    """A parameter passed to a parameterized Cosmos DB query."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Cosmos SQL parameter name, including the @ prefix.")
    value: Any = Field(description="JSON-serializable parameter value.")
