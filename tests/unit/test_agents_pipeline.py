from __future__ import annotations

from src.agents import PipelineDocumentInput, build_pipeline
from src.config import AgentsConfig
from src.models import DocumentType, TriageResult


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
    pipeline = build_pipeline(config=AgentsConfig(), credential=object(), project_endpoint="https://foundry.example")
    workflow = pipeline.build_workflow(PipelineDocumentInput(document_reference="https://storage/doc.pdf"))

    assert set(pipeline.agents) == {"triage", "extractor", "coherence", "validator", "inventory", "communication"}
    assert pipeline.communication_agent is pipeline.agents["communication"]
    assert workflow is not None


def test_triage_result_model_round_trip() -> None:
    payload = TriageResult(
        document_type=DocumentType.ALBARAN,
        confidence=0.91,
        routing_decision="extract",
        reasoning="Contains delivery note language and supplier header.",
    )

    restored = TriageResult.model_validate_json(payload.model_dump_json())

    assert restored.document_type is DocumentType.ALBARAN
    assert restored.routing_decision == "extract"
