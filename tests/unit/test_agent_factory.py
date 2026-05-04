from __future__ import annotations

from typing import Any
from unittest.mock import call, patch

import pytest

from src.agents.factory import create_all_agents
from src.config.agents import AgentsConfig

pytestmark = pytest.mark.unit


def test_create_all_agents_returns_expected_keys() -> None:
    agents = create_all_agents(config=AgentsConfig(), credential=object(), project_endpoint="https://foundry.example")

    assert set(agents) == {"triage", "extractor", "coherence", "validator", "inventory", "communication"}


@patch("src.agents.factory.create_foundry_client", side_effect=["gpt5-client", "gpt5-mini-client"])
@patch("src.agents.factory.create_communication_agent", return_value="communication-agent")
@patch("src.agents.factory.create_inventory_agent", return_value="inventory-agent")
@patch("src.agents.factory.create_validator_agent", return_value="validator-agent")
@patch("src.agents.factory.create_coherence_agent", return_value="coherence-agent")
@patch("src.agents.factory.create_extractor_agent", return_value="extractor-agent")
@patch("src.agents.factory.create_triage_agent", return_value="triage-agent")
def test_create_all_agents_passes_tool_registry_to_each_agent(
    mock_triage: Any,
    mock_extractor: Any,
    mock_coherence: Any,
    mock_validator: Any,
    mock_inventory: Any,
    mock_communication: Any,
    mock_create_foundry_client: Any,
) -> None:
    config = AgentsConfig()
    tool_registry = {
        "triage": ["triage-tool"],
        "extractor": ["extractor-tool"],
        "coherence": ["coherence-tool"],
        "validator": ["validator-tool"],
        "inventory": ["inventory-tool"],
        "communication": ["communication-tool"],
    }

    agents = create_all_agents(
        config=config,
        credential="credential",
        project_endpoint="https://foundry.example",
        tool_registry=tool_registry,
    )

    assert agents == {
        "triage": "triage-agent",
        "extractor": "extractor-agent",
        "coherence": "coherence-agent",
        "validator": "validator-agent",
        "inventory": "inventory-agent",
        "communication": "communication-agent",
    }
    mock_create_foundry_client.assert_has_calls(
        [
            call(
                project_endpoint="https://foundry.example",
                model=config.models.gpt5_deployment,
                credential="credential",
            ),
            call(
                project_endpoint="https://foundry.example",
                model=config.models.gpt5_mini_deployment,
                credential="credential",
            ),
        ]
    )
    mock_triage.assert_called_once_with("gpt5-mini-client", config, tools=["triage-tool"])
    mock_extractor.assert_called_once_with("gpt5-client", config, tools=["extractor-tool"])
    mock_coherence.assert_called_once_with("gpt5-mini-client", config, tools=["coherence-tool"])
    mock_validator.assert_called_once_with("gpt5-mini-client", config, tools=["validator-tool"])
    mock_inventory.assert_called_once_with("gpt5-mini-client", config, tools=["inventory-tool"])
    mock_communication.assert_called_once_with("gpt5-mini-client", config, tools=["communication-tool"])


@patch("src.agents.factory.create_foundry_client", side_effect=["extractor-client", "shared-mini-client"])
@patch("src.agents.factory.create_communication_agent", return_value="communication-local-agent")
@patch("src.agents.factory.create_inventory_agent", return_value="inventory-local-agent")
@patch("src.agents.factory.create_validator_agent", return_value="validator-local-agent")
@patch("src.agents.factory.create_coherence_agent", return_value="coherence-local-agent")
@patch("src.agents.factory.create_extractor_agent", return_value="extractor-local-agent")
@patch("src.agents.factory.create_triage_agent", return_value="triage-local-agent")
def test_create_all_agents_respects_custom_config_overrides(
    mock_triage: Any,
    mock_extractor: Any,
    mock_coherence: Any,
    mock_validator: Any,
    mock_inventory: Any,
    mock_communication: Any,
    mock_create_foundry_client: Any,
) -> None:
    custom_config = AgentsConfig.model_validate(
        {
            "models": {
                "gpt5_deployment": "extractor-local",
                "gpt5_mini_deployment": "shared-mini-local",
            }
        }
    )

    agents = create_all_agents(
        config=custom_config,
        credential="credential",
        project_endpoint="https://foundry.example",
    )

    assert agents == {
        "triage": "triage-local-agent",
        "extractor": "extractor-local-agent",
        "coherence": "coherence-local-agent",
        "validator": "validator-local-agent",
        "inventory": "inventory-local-agent",
        "communication": "communication-local-agent",
    }
    mock_create_foundry_client.assert_has_calls(
        [
            call(
                project_endpoint="https://foundry.example",
                model="extractor-local",
                credential="credential",
            ),
            call(
                project_endpoint="https://foundry.example",
                model="shared-mini-local",
                credential="credential",
            ),
        ]
    )
    assert mock_triage.call_args.args[1].models.gpt5_mini_deployment == "shared-mini-local"
    assert mock_extractor.call_args.args[1].models.gpt5_deployment == "extractor-local"
    assert mock_coherence.call_args.args[1].models.gpt5_mini_deployment == "shared-mini-local"
    assert mock_validator.call_args.args[1].models.gpt5_mini_deployment == "shared-mini-local"
    assert mock_inventory.call_args.args[1].models.gpt5_mini_deployment == "shared-mini-local"
    assert mock_communication.call_args.args[1].models.gpt5_mini_deployment == "shared-mini-local"
