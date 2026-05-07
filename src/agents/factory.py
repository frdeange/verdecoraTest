from __future__ import annotations

import importlib
import os
from collections.abc import Mapping, Sequence
from typing import Any

from agent_framework import Agent

from src.models.albaran import AlbaranExtraction, CoherenceCheckResult, TriageResult
from src.models.inventory import PostingResult
from src.models.learning import LearningReport
from src.models.reconciliation import ReconciliationReport
from src.models.validation import ValidationResult

from .communication_agent import CommunicationSummary
from .prompts import (
    build_coherence_instructions,
    build_communication_instructions,
    build_extractor_instructions,
    build_inventory_instructions,
    build_learning_instructions,
    build_reconciliation_instructions,
    build_triage_instructions,
    build_validator_instructions,
)

ToolRegistry = Mapping[str, Sequence[Any]]
DEFAULT_GPT5_MAX_TOKENS = 1200


def _load_foundry_chat_client() -> type[Any]:
    module = importlib.import_module("agent_framework.foundry")
    return module.FoundryChatClient


def _resolve_tool_names(tools: Sequence[Any]) -> tuple[str, ...]:
    return tuple(getattr(tool, "name", str(tool)) for tool in tools)


def _default_options(response_format: type[Any]) -> dict[str, Any]:
    return {"response_format": response_format, "max_tokens": DEFAULT_GPT5_MAX_TOKENS}


def create_clients(project_endpoint: str, credential: Any) -> tuple[Any, Any]:
    """Create GPT-5 and GPT-5-mini Foundry chat clients."""

    foundry_chat_client = _load_foundry_chat_client()
    gpt5 = foundry_chat_client(
        project_endpoint=project_endpoint,
        model=os.getenv("GPT5_DEPLOYMENT", "gpt-5"),
        credential=credential,
    )
    gpt5_mini = foundry_chat_client(
        project_endpoint=project_endpoint,
        model=os.getenv("GPT5_MINI_DEPLOYMENT", "gpt-5-mini"),
        credential=credential,
    )
    return gpt5, gpt5_mini


def create_agents(
    gpt5: Any,
    gpt5_mini: Any,
    *,
    mcp_tools: ToolRegistry | None = None,
) -> dict[str, Agent]:
    """Create all MAF agents for the albarán pipeline."""

    tools = {key: list(value) for key, value in (mcp_tools or {}).items()}
    extractor_tools = tools.get("extractor", [])
    coherence_tools = tools.get("coherence", [])
    validator_tools = tools.get("validator", [])
    inventory_tools = tools.get("inventory", [])
    communication_tools = tools.get("communication", [])
    reconciliation_tools = tools.get("reconciliation", [])
    learning_tools = tools.get("learning", [])

    return {
        "triage": Agent(
            gpt5_mini,
            name="Triage",
            instructions=build_triage_instructions(),
            default_options=_default_options(TriageResult),
        ),
        "extractor": Agent(
            gpt5,
            name="Extractor",
            instructions=build_extractor_instructions(_resolve_tool_names(extractor_tools)),
            default_options=_default_options(AlbaranExtraction),
            tools=extractor_tools,
        ),
        "coherence": Agent(
            gpt5_mini,
            name="Coherence",
            instructions=build_coherence_instructions(_resolve_tool_names(coherence_tools)),
            default_options=_default_options(CoherenceCheckResult),
            tools=coherence_tools,
        ),
        "validator": Agent(
            gpt5_mini,
            name="Validator",
            instructions=build_validator_instructions(_resolve_tool_names(validator_tools)),
            default_options=_default_options(ValidationResult),
            tools=validator_tools,
        ),
        "inventory": Agent(
            gpt5_mini,
            name="Inventory",
            instructions=build_inventory_instructions(_resolve_tool_names(inventory_tools)),
            default_options=_default_options(PostingResult),
            tools=inventory_tools,
        ),
        "communication": Agent(
            gpt5_mini,
            name="Communication",
            instructions=build_communication_instructions(),
            default_options=_default_options(CommunicationSummary),
            tools=communication_tools,
        ),
        "reconciliation": Agent(
            gpt5_mini,
            name="Reconciliation",
            instructions=build_reconciliation_instructions(_resolve_tool_names(reconciliation_tools)),
            default_options=_default_options(ReconciliationReport),
            tools=reconciliation_tools,
        ),
        "learning": Agent(
            gpt5_mini,
            name="Learning",
            instructions=build_learning_instructions(_resolve_tool_names(learning_tools)),
            default_options=_default_options(LearningReport),
            tools=learning_tools,
        ),
    }


__all__ = ["Agent", "ToolRegistry", "create_agents", "create_clients"]
