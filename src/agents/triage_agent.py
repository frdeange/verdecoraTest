from __future__ import annotations

import json
from typing import Any

from src.config.agents import AgentsConfig, get_agents_config
from src.models.albaran import TriageResult

from ._maf_compat import create_structured_agent
from .prompts import TRIAGE_SYSTEM_PROMPT
from .security import harden_system_prompt


def _build_triage_instructions() -> str:
    schema = json.dumps(TriageResult.model_json_schema(), ensure_ascii=False, indent=2)
    return harden_system_prompt(TRIAGE_SYSTEM_PROMPT.format(schema=schema))


def create_triage_agent(
    client: Any,
    config: AgentsConfig | None = None,
    *,
    tools: list[Any] | None = None,
) -> Any:
    resolved_config = config or get_agents_config()
    return create_structured_agent(
        client=client,
        name="a2-triage",
        model=resolved_config.models.gpt5_mini_deployment,
        instructions=_build_triage_instructions(),
        structured_output=TriageResult,
        tools=tools,
        handoffs=["a1-extractor", "user"],
    )
