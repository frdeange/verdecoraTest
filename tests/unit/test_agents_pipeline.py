from __future__ import annotations

from src.agents import PipelineDocumentInput, build_pipeline
from src.config import AgentsConfig
from src.models import DocumentType, TriageResult


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


def test_pipeline_builds_with_default_agents() -> None:
    pipeline = build_pipeline(client=object(), config=AgentsConfig())
    workflow = pipeline.build_workflow(PipelineDocumentInput(document_reference="https://storage/doc.pdf"))

    assert set(pipeline.agents) == {"triage", "extractor", "coherence", "validator", "inventory"}
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
