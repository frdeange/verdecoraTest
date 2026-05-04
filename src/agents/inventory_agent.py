from __future__ import annotations

import json
from typing import Any

from src.config.agents import AgentsConfig, get_agents_config
from src.models.inventory import PostingResult
from src.models.validation import ValidationResult

from ._maf_compat import create_structured_agent
from .prompts import INVENTORY_SYSTEM_PROMPT
from .security import harden_system_prompt

DEFAULT_INVENTORY_TOOL_NAMES: tuple[str, ...] = (
    "bc.create_purchase_receipt",
    "bc.post_purchase_receipt_lines",
)


def _build_inventory_instructions(tool_names: tuple[str, ...]) -> str:
    schema = json.dumps(PostingResult.model_json_schema(), ensure_ascii=False, indent=2)
    tool_hint = "\nAvailable MCP tools: " + ", ".join(tool_names) if tool_names else ""
    return harden_system_prompt(INVENTORY_SYSTEM_PROMPT.format(schema=schema) + tool_hint)


def create_inventory_agent(
    client: Any,
    config: AgentsConfig | None = None,
    *,
    tools: list[Any] | None = None,
) -> Any:
    resolved_config = config or get_agents_config()
    resolved_tools = list(tools or [])
    tool_names = tuple(getattr(tool, "name", str(tool)) for tool in resolved_tools) or DEFAULT_INVENTORY_TOOL_NAMES
    return create_structured_agent(
        client=client,
        name="a5-inventory",
        model=resolved_config.models.inventory_model,
        instructions=_build_inventory_instructions(tool_names),
        structured_output=PostingResult,
        tools=resolved_tools,
        handoffs=["user"],
    )


def should_process_inventory(validation_result: ValidationResult | dict[str, Any] | None) -> bool:
    if validation_result is None:
        return False
    normalized_result = validation_result
    if not isinstance(validation_result, ValidationResult):
        normalized_result = ValidationResult.model_validate(validation_result)
    return normalized_result.is_valid and normalized_result.recommendation == "approve"


def build_posting_failure_result(
    error: Exception | str,
    *,
    receipt_number: str | None = None,
    posted_lines: int = 0,
    bc_document_url: str | None = None,
) -> PostingResult:
    message = str(error).strip() or "Business Central posting failed."
    return PostingResult(
        success=False,
        receipt_number=receipt_number,
        posted_lines=posted_lines,
        errors=[message],
        bc_document_url=bc_document_url,
    )


__all__ = [
    "DEFAULT_INVENTORY_TOOL_NAMES",
    "build_posting_failure_result",
    "create_inventory_agent",
    "should_process_inventory",
]
