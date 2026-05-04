from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.config.agents import AgentsConfig, get_agents_config

pytestmark = pytest.mark.unit


def test_agents_config_defaults() -> None:
    config = AgentsConfig()

    assert config.endpoints.azure_openai_endpoint == "https://verdecora-openai-dev.openai.azure.com/"
    assert config.endpoints.document_intelligence_endpoint == (
        "https://verdecora-docintell-dev.cognitiveservices.azure.com/"
    )
    assert config.models.extractor_model == "gpt-5"
    assert config.models.triage_model == "gpt-5-mini"
    assert config.models.coherence_model == "gpt-5-mini"
    assert config.models.validator_model == "gpt-5-mini"
    assert config.models.inventory_model == "gpt-5-mini"
    assert config.models.communication_model == "gpt-5-mini"
    assert config.thresholds.triage_manual_review_threshold == pytest.approx(0.65)
    assert config.thresholds.low_value_coherence_threshold == pytest.approx(250.0)
    assert config.skip_triage_suppliers == ()


@patch.dict(
    "os.environ",
    {
        "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/",
        "DOCUMENT_INTELLIGENCE_ENDPOINT": "https://example-docint.cognitiveservices.azure.com/",
        "AZURE_OPENAI_API_VERSION": "2025-01-01-preview",
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

    assert config.endpoints.azure_openai_endpoint == "https://example.openai.azure.com/"
    assert config.endpoints.document_intelligence_endpoint == "https://example-docint.cognitiveservices.azure.com/"
    assert config.endpoints.azure_openai_api_version == "2025-01-01-preview"
    assert config.models.extractor_model == "gpt-5-custom"
    assert config.models.triage_model == "gpt-5-mini-custom"
    assert config.models.coherence_model == "gpt-5-mini-custom"
    assert config.models.validator_model == "gpt-5-mini-custom"
    assert config.models.inventory_model == "gpt-5-mini-custom"
    assert config.models.communication_model == "gpt-5-mini-custom"
    assert config.thresholds.triage_manual_review_threshold == pytest.approx(0.7)
    assert config.thresholds.low_value_coherence_threshold == pytest.approx(99.5)
    assert config.skip_triage_suppliers == ("HERSTERA", "ROYAL CANIN")


@pytest.mark.parametrize(
    "payload",
    [
        {"thresholds": {"triage_manual_review_threshold": "invalid"}},
        {"models": {"extractor_model": None}},
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
