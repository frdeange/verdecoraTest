from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Store(BaseModel):
    """Canonical store master data shared by the upload app and BC integration."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    region: str
    address: str
    city: str
    postal_code: str
    aliases: list[str] = Field(default_factory=list)
    bc_location_code: str = ""
