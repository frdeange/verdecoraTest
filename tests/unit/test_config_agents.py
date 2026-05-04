from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.config.agents import AgentsConfig, get_agents_config

pytestmark = pytest.mark.unit


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
    assert config.thresholds.triage_manual_review_threshold == pytest.approx(0.65)
    assert config.thresholds.low_value_coherence_threshold == pytest.approx(250.0)
    assert config.skip_triage_suppliers == ()


@patch.dict(
    "os.environ",
    {
        "AZURE_AI_PROJECT_ENDPOINT": "https://example.services.ai.azure.com/api/projects/demo",
        "DOCUMENT_INTELLIGENCE_ENDPOINT": "https://example-docint.cognitiveservices.azure.com/",
        "GPT5_DEPLOYMENT": "gpt-5-custom",
        "GPT5_MINI_DEPLOYMENT": "gpt-5-mini-custom",
        "TRIAGE_MANUAL_REVIEW_THRESHOLD": "0.7",
        "LOW_VALUE_COHERENCE_THRESHOLD": "99.5",
        "SKIP_TRIAGE_SUPPLIERS": "HERSTERA, ROYAL CANIN",
    },
    clear=False,
)
def test_agents_config_reads_environment_overrides() -> None:
    get_agents_config.cache_clear()
    config = AgentsConfig()

    assert config.endpoints.azure_ai_project_endpoint == "https://example.services.ai.azure.com/api/projects/demo"
    assert config.endpoints.document_intelligence_endpoint == "https://example-docint.cognitiveservices.azure.com/"
    assert config.models.gpt5_deployment == "gpt-5-custom"
    assert config.models.gpt5_mini_deployment == "gpt-5-mini-custom"
    assert config.thresholds.triage_manual_review_threshold == pytest.approx(0.7)
    assert config.thresholds.low_value_coherence_threshold == pytest.approx(99.5)
    assert config.skip_triage_suppliers == ("HERSTERA", "ROYAL CANIN")


@pytest.mark.parametrize(
    "payload",
    [
        {"thresholds": {"triage_manual_review_threshold": "invalid"}},
        {"models": {"gpt5_deployment": None}},
        {"skip_triage_suppliers": None},
    ],
)
def test_agents_config_validation_rejects_invalid_payloads(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        AgentsConfig.model_validate(payload)


def test_get_agents_config_is_cached() -> None:
    get_agents_config.cache_clear()

    first = get_agents_config()
    second = get_agents_config()

    assert first is second
