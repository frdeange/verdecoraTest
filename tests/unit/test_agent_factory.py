from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from src.agents.factory import create_all_agents
from src.config.agents import AgentsConfig

pytestmark = pytest.mark.unit


def test_create_all_agents_returns_expected_keys() -> None:
    agents = create_all_agents(client=object(), config=AgentsConfig())

    assert set(agents) == {"triage", "extractor", "coherence"}


@patch("src.agents.factory.create_coherence_agent", return_value="coherence-agent")
@patch("src.agents.factory.create_extractor_agent", return_value="extractor-agent")
@patch("src.agents.factory.create_triage_agent", return_value="triage-agent")
def test_create_all_agents_passes_tool_registry_to_each_agent(
    mock_triage: Any, mock_extractor: Any, mock_coherence: Any
) -> None:
    config = AgentsConfig()
    tool_registry = {
        "triage": ["triage-tool"],
        "extractor": ["extractor-tool"],
        "coherence": ["coherence-tool"],
    }

    agents = create_all_agents(client="client", config=config, tool_registry=tool_registry)

    assert agents == {
        "triage": "triage-agent",
        "extractor": "extractor-agent",
        "coherence": "coherence-agent",
    }
    mock_triage.assert_called_once_with("client", config, tools=["triage-tool"])
    mock_extractor.assert_called_once_with("client", config, tools=["extractor-tool"])
    mock_coherence.assert_called_once_with("client", config, tools=["coherence-tool"])


@patch("src.agents.factory.create_coherence_agent", return_value="coherence-local-agent")
@patch("src.agents.factory.create_extractor_agent", return_value="extractor-local-agent")
@patch("src.agents.factory.create_triage_agent", return_value="triage-local-agent")
def test_create_all_agents_respects_custom_config_overrides(
    mock_triage: Any, mock_extractor: Any, mock_coherence: Any
) -> None:
    custom_config = AgentsConfig.model_validate(
        {
            "models": {
                "triage_model": "triage-local",
                "extractor_model": "extractor-local",
                "coherence_model": "coherence-local",
            }
        }
    )

    agents = create_all_agents(client="client", config=custom_config)

    assert agents == {
        "triage": "triage-local-agent",
        "extractor": "extractor-local-agent",
        "coherence": "coherence-local-agent",
    }
    assert mock_triage.call_args.args[1].models.triage_model == "triage-local"
    assert mock_extractor.call_args.args[1].models.extractor_model == "extractor-local"
    assert mock_coherence.call_args.args[1].models.coherence_model == "coherence-local"
