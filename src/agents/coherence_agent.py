from __future__ import annotations

import json
from typing import Any

from src.config.agents import AgentsConfig, get_agents_config
from src.models.albaran import CoherenceCheckResult

from ._maf_compat import create_structured_agent
from .prompts import COHERENCE_SYSTEM_PROMPT

DEFAULT_COHERENCE_TOOL_NAMES: tuple[str, ...] = (
    "bc.search_vendors",
    "bc.search_purchase_orders",
    "bc.search_items",
)


def _build_coherence_instructions(tool_names: tuple[str, ...]) -> str:
    schema = json.dumps(CoherenceCheckResult.model_json_schema(), ensure_ascii=False, indent=2)
    tool_hint = "\nAvailable MCP tools: " + ", ".join(tool_names) if tool_names else ""
    return COHERENCE_SYSTEM_PROMPT.format(schema=schema) + tool_hint


def create_coherence_agent(
    client: Any,
    config: AgentsConfig | None = None,
    *,
    tools: list[Any] | None = None,
) -> Any:
    resolved_config = config or get_agents_config()
    resolved_tools = list(tools or [])
    tool_names = tuple(getattr(tool, "name", str(tool)) for tool in resolved_tools) or DEFAULT_COHERENCE_TOOL_NAMES
    return create_structured_agent(
        client=client,
        name="a3-coherence",
        model=resolved_config.models.coherence_model,
        instructions=_build_coherence_instructions(tool_names),
        structured_output=CoherenceCheckResult,
        tools=resolved_tools,
    )
