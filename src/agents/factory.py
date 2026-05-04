from __future__ import annotations

from typing import Any, Mapping

from src.config.agents import AgentsConfig, get_agents_config

from ._maf_compat import create_foundry_client
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
    config: AgentsConfig | None = None,
    *,
    credential: Any | None = None,
    project_endpoint: str | None = None,
    gpt5_client: Any | None = None,
    gpt5_mini_client: Any | None = None,
    tool_registry: ToolRegistry | None = None,
) -> dict[str, Any]:
    resolved_config = config or get_agents_config()
    resolved_project_endpoint = project_endpoint or resolved_config.endpoints.azure_ai_project_endpoint
    resolved_credential = credential or resolved_config.create_credential()
    resolved_gpt5_client = gpt5_client or create_foundry_client(
        project_endpoint=resolved_project_endpoint,
        model=resolved_config.models.gpt5_deployment,
        credential=resolved_credential,
    )
    resolved_gpt5_mini_client = gpt5_mini_client or create_foundry_client(
        project_endpoint=resolved_project_endpoint,
        model=resolved_config.models.gpt5_mini_deployment,
        credential=resolved_credential,
    )
    return {
        "triage": create_triage_agent(
            resolved_gpt5_mini_client, resolved_config, tools=_get_tools(tool_registry, "triage")
        ),
        "extractor": create_extractor_agent(
            resolved_gpt5_client, resolved_config, tools=_get_tools(tool_registry, "extractor")
        ),
        "coherence": create_coherence_agent(
            resolved_gpt5_mini_client, resolved_config, tools=_get_tools(tool_registry, "coherence")
        ),
        "validator": create_validator_agent(
            resolved_gpt5_mini_client, resolved_config, tools=_get_tools(tool_registry, "validator")
        ),
        "inventory": create_inventory_agent(
            resolved_gpt5_mini_client, resolved_config, tools=_get_tools(tool_registry, "inventory")
        ),
        "communication": create_communication_agent(
            resolved_gpt5_mini_client, resolved_config, tools=_get_tools(tool_registry, "communication")
        ),
    }
