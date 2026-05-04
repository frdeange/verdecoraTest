from __future__ import annotations

from typing import Any, Mapping

from src.config.agents import AgentsConfig, get_agents_config

from .coherence_agent import create_coherence_agent
from .communication_agent import create_communication_agent
from .extractor_agent import create_extractor_agent
from .inventory_agent import create_inventory_agent
from .triage_agent import create_triage_agent
from .validator_agent import create_validator_agent

ToolRegistry = Mapping[str, list[Any]]


def _get_tools(tool_registry: ToolRegistry | None, key: str) -> list[Any] | None:
    if tool_registry is None:
        return None
    return list(tool_registry.get(key, []))


def create_all_agents(
    client: Any,
    config: AgentsConfig | None = None,
    *,
    tool_registry: ToolRegistry | None = None,
) -> dict[str, Any]:
    resolved_config = config or get_agents_config()
    return {
        "triage": create_triage_agent(client, resolved_config, tools=_get_tools(tool_registry, "triage")),
        "extractor": create_extractor_agent(client, resolved_config, tools=_get_tools(tool_registry, "extractor")),
        "coherence": create_coherence_agent(client, resolved_config, tools=_get_tools(tool_registry, "coherence")),
        "validator": create_validator_agent(client, resolved_config, tools=_get_tools(tool_registry, "validator")),
        "inventory": create_inventory_agent(client, resolved_config, tools=_get_tools(tool_registry, "inventory")),
        "communication": create_communication_agent(
            client, resolved_config, tools=_get_tools(tool_registry, "communication")
        ),
    }
