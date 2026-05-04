from __future__ import annotations

import json
from typing import Any

from src.config.agents import AgentsConfig, get_agents_config
from src.models.validation import ValidationResult, compare_line_values, recommend_validation_action

from ._maf_compat import create_structured_agent
from .prompts import VALIDATOR_SYSTEM_PROMPT

DEFAULT_VALIDATOR_TOOL_NAMES: tuple[str, ...] = (
    "bc.search_purchase_orders",
    "bc.get_purchase_order_lines",
    "bc.search_items",
)


def _build_validator_instructions(tool_names: tuple[str, ...]) -> str:
    schema = json.dumps(ValidationResult.model_json_schema(), ensure_ascii=False, indent=2)
    tool_hint = "\nAvailable MCP tools: " + ", ".join(tool_names) if tool_names else ""
    return VALIDATOR_SYSTEM_PROMPT.format(schema=schema) + tool_hint


def create_validator_agent(
    client: Any,
    config: AgentsConfig | None = None,
    *,
    tools: list[Any] | None = None,
) -> Any:
    resolved_config = config or get_agents_config()
    resolved_tools = list(tools or [])
    tool_names = tuple(getattr(tool, "name", str(tool)) for tool in resolved_tools) or DEFAULT_VALIDATOR_TOOL_NAMES
    return create_structured_agent(
        client=client,
        name="a4-validator",
        model=resolved_config.models.validator_model,
        instructions=_build_validator_instructions(tool_names),
        structured_output=ValidationResult,
        tools=resolved_tools,
        handoffs=["a5-inventory", "user"],
    )


__all__ = [
    "DEFAULT_VALIDATOR_TOOL_NAMES",
    "compare_line_values",
    "create_validator_agent",
    "recommend_validation_action",
]
