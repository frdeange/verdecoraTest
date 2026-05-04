from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from src.agents import AlbaranPipeline
from src.config import AgentsConfig


def _named_agents() -> dict[str, Any]:
    return {
        "triage": SimpleNamespace(name="triage"),
        "extractor": SimpleNamespace(name="extractor"),
        "coherence": SimpleNamespace(name="coherence"),
        "validator": SimpleNamespace(name="validator"),
        "inventory": SimpleNamespace(name="inventory"),
        "communication": SimpleNamespace(name="communication"),
    }


def test_agents_config_defaults() -> None:
    config = AgentsConfig()

    assert config.endpoints.azure_ai_project_endpoint == (
        "https://verdecora-ais-dev.services.ai.azure.com/api/projects/verdecora-project-dev"
    )
    assert config.endpoints.document_intelligence_endpoint == (
        "https://verdecora-docintell-dev.cognitiveservices.azure.com/"
    )
    assert config.models.gpt5_deployment == "gpt-5"
    assert config.models.gpt5_mini_deployment == "gpt-5-mini"


def test_pipeline_builds_with_default_agents() -> None:
    with (
        patch("src.agents.pipeline.create_clients", return_value=("gpt5", "gpt5-mini")),
        patch("src.agents.pipeline.create_agents", return_value=_named_agents()),
        patch("src.agents.pipeline.SequentialBuilder") as mock_builder,
    ):
        workflow = object()
        mock_builder.return_value.build.return_value = workflow
        pipeline = AlbaranPipeline(
            config=AgentsConfig(), credential=object(), project_endpoint="https://foundry.example"
        )
        built = pipeline.build_workflow()

    assert set(pipeline.agents) == {"triage", "extractor", "coherence", "validator", "inventory", "communication"}
    assert pipeline.communication_agent is pipeline.agents["communication"]
    assert built is workflow
    participants = mock_builder.call_args.kwargs["participants"]
    assert [participant.name for participant in participants] == [
        "triage",
        "extractor",
        "coherence",
        "validator",
        "inventory",
    ]
