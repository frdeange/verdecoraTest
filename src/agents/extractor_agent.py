from __future__ import annotations

import json
from typing import Any

from src.config.agents import AgentsConfig, get_agents_config
from src.models.albaran import AlbaranExtraction

from ._maf_compat import create_structured_agent
from .prompts import EXTRACTOR_SYSTEM_PROMPT

DEFAULT_EXTRACTOR_TOOL_NAMES: tuple[str, ...] = (
    "content_understanding.analyze_document",
    "content_understanding.extract_tables",
)


def _build_extractor_instructions(tool_names: tuple[str, ...]) -> str:
    schema = json.dumps(AlbaranExtraction.model_json_schema(), ensure_ascii=False, indent=2)
    tool_hint = "\nAvailable MCP tools: " + ", ".join(tool_names) if tool_names else ""
    return EXTRACTOR_SYSTEM_PROMPT.format(schema=schema) + tool_hint


def create_extractor_agent(
    client: Any,
    config: AgentsConfig | None = None,
    *,
    tools: list[Any] | None = None,
) -> Any:
    resolved_config = config or get_agents_config()
    resolved_tools = list(tools or [])
    tool_names = tuple(getattr(tool, "name", str(tool)) for tool in resolved_tools) or DEFAULT_EXTRACTOR_TOOL_NAMES
    return create_structured_agent(
        client=client,
        name="a1-extractor",
        model=resolved_config.models.extractor_model,
        instructions=_build_extractor_instructions(tool_names),
        structured_output=AlbaranExtraction,
        tools=resolved_tools,
        handoffs=["a3-coherence"],
    )
