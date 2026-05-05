from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from unittest.mock import patch

import pytest

from src.agents.factory import create_agents, create_clients
from src.models.albaran import AlbaranExtraction, CoherenceCheckResult, TriageResult
from src.models.inventory import PostingResult
from src.models.learning import LearningReport
from src.models.reconciliation import ReconciliationReport
from src.models.validation import ValidationResult
from tests.unit.agent_test_helpers import StructuredAgentStub, build_structured_agent_stub

pytestmark = pytest.mark.unit


class DummyFoundryChatClient:
    def __init__(self, *, project_endpoint: str, model: str, credential: Any) -> None:
        self.project_endpoint = project_endpoint
        self.model = model
        self.credential = credential


class NamedTool:
    def __init__(self, name: str) -> None:
        self.name = name


def test_create_clients_uses_foundry_models_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GPT5_DEPLOYMENT", "gpt-5-test")
    monkeypatch.setenv("GPT5_MINI_DEPLOYMENT", "gpt-5-mini-test")

    with patch("src.agents.factory._load_foundry_chat_client", return_value=DummyFoundryChatClient):
        gpt5, gpt5_mini = create_clients("https://foundry.example", credential="credential")

    assert gpt5.model == "gpt-5-test"
    assert gpt5_mini.model == "gpt-5-mini-test"
    assert gpt5.project_endpoint == "https://foundry.example"
    assert gpt5_mini.credential == "credential"


@patch("src.agents.factory.Agent", side_effect=build_structured_agent_stub)
def test_create_agents_returns_expected_keys_and_models(mock_agent: Any) -> None:
    tool_registry = {
        "extractor": [NamedTool("content_understanding.analyze_document")],
        "coherence": [NamedTool("bc.search_purchase_orders")],
        "validator": [NamedTool("bc.get_purchase_order_lines")],
        "inventory": [NamedTool("bc.post_purchase_receipt_lines")],
        "communication": [NamedTool("acs.send_hitl_notification")],
        "reconciliation": [NamedTool("cosmos.query_documents")],
        "learning": [NamedTool("feature_flags.set_supplier_config")],
    }

    agents = create_agents("gpt5-client", "gpt5-mini-client", mcp_tools=tool_registry)

    assert set(agents) == {
        "triage",
        "extractor",
        "coherence",
        "validator",
        "inventory",
        "communication",
        "reconciliation",
        "learning",
    }
    assert mock_agent.call_count == 8

    triage = agents["triage"]
    extractor = agents["extractor"]
    coherence = agents["coherence"]
    validator = agents["validator"]
    inventory = agents["inventory"]
    communication = agents["communication"]
    reconciliation = agents["reconciliation"]
    learning = agents["learning"]

    assert isinstance(triage, StructuredAgentStub)
    assert triage.kwargs["client"] == "gpt5-mini-client"
    assert triage.kwargs["default_options"]["response_format"] is TriageResult
    assert "document triage specialist" in triage.kwargs["instructions"]

    assert extractor.kwargs["client"] == "gpt5-client"
    assert extractor.kwargs["default_options"]["response_format"] is AlbaranExtraction
    assert extractor.kwargs["tools"] == tool_registry["extractor"]

    assert coherence.kwargs["client"] == "gpt5-mini-client"
    assert coherence.kwargs["default_options"]["response_format"] is CoherenceCheckResult
    assert "bc.search_purchase_orders" in coherence.kwargs["instructions"]

    assert validator.kwargs["default_options"]["response_format"] is ValidationResult
    assert validator.kwargs["tools"] == tool_registry["validator"]

    assert inventory.kwargs["default_options"]["response_format"] is PostingResult
    assert inventory.kwargs["tools"] == tool_registry["inventory"]

    assert communication.kwargs["tools"] == tool_registry["communication"]
    assert "español" in communication.kwargs["instructions"]

    assert reconciliation.kwargs["response_format"] is ReconciliationReport
    assert "cosmos.query_documents" in reconciliation.kwargs["instructions"]

    assert learning.kwargs["response_format"] is LearningReport
    assert "feature_flags.set_supplier_config" in learning.kwargs["instructions"]


def test_create_agents_omits_optional_tool_lists_when_not_provided() -> None:
    captured_calls: list[dict[str, Any]] = []

    def fake_agent(*args: Any, **kwargs: Any) -> dict[str, Any]:
        if args:
            kwargs["client"] = args[0]
        captured_calls.append(kwargs)
        return kwargs

    with patch("src.agents.factory.Agent", side_effect=fake_agent):
        agents = create_agents("gpt5-client", "gpt5-mini-client")

    assert set(agents) == {
        "triage",
        "extractor",
        "coherence",
        "validator",
        "inventory",
        "communication",
        "reconciliation",
        "learning",
    }
    tool_payloads = [call.get("tools") for call in captured_calls if "tools" in call]
    assert all(isinstance(payload, Sequence) for payload in tool_payloads)
