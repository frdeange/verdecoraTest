from __future__ import annotations

from pydantic import BaseModel, Field


class PageGroup(BaseModel):
    """Suggested grouping of pages into a single albarán."""

    group_id: str
    page_indices: list[int] = Field(default_factory=list)
    suggested_supplier: str | None = None
    suggested_date: str | None = None
    suggested_albaran_number: str | None = None


class PreflightResult(BaseModel):
    """Full preflight analysis returned to the UI."""

    session_id: str
    files_analyzed: int
    detected_supplier: str | None = None
    detected_date: str | None = None
    detected_albaran_number: str | None = None
    detected_store: str | None = None
    confidence: float = 0.0
    is_albaran: bool = False
    warnings: list[str] = Field(default_factory=list)
    page_groups: list[PageGroup] = Field(default_factory=list)
