from __future__ import annotations

import inspect
from typing import Any, Mapping, TypeVar

from pydantic import BaseModel, Field

from src.config.agents import AgentsConfig, get_agents_config
from src.models.albaran import AlbaranExtraction, CoherenceCheckResult, TriageResult

from ._maf_compat import build_sequential_workflow, coerce_model, ensure_workflow_available, event_payload
from .factory import ToolRegistry, create_all_agents

T = TypeVar("T", TriageResult, AlbaranExtraction, CoherenceCheckResult)


class PipelineDocumentInput(BaseModel):
    document_reference: str
    raw_text: str | None = None
    ocr_payload: dict[str, Any] | str | None = None
    supplier_id: str | None = None
    supplier_hint: str | None = None
    total_amount: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineRunResult(BaseModel):
    triage: TriageResult | None = None
    extraction: AlbaranExtraction | None = None
    coherence: CoherenceCheckResult | None = None
    routing_decision: str
    skipped_steps: list[str] = Field(default_factory=list)


class AlbaranPipeline:
    def __init__(
        self,
        client: Any,
        config: AgentsConfig | None = None,
        *,
        tool_registry: ToolRegistry | None = None,
        agents: Mapping[str, Any] | None = None,
    ) -> None:
        self.client = client
        self.config = config or get_agents_config()
        self.agents = dict(agents or create_all_agents(client, self.config, tool_registry=tool_registry))

    def _should_skip_triage(self, input_data: PipelineDocumentInput) -> bool:
        supplier_tokens = {token.casefold() for token in self.config.skip_triage_suppliers}
        return any(
            candidate.casefold() in supplier_tokens
            for candidate in (input_data.supplier_id, input_data.supplier_hint)
            if candidate
        )

    def _should_skip_coherence(self, input_data: PipelineDocumentInput) -> bool:
        if input_data.total_amount is None:
            return False
        return input_data.total_amount < self.config.thresholds.low_value_coherence_threshold

    def build_workflow(self, input_data: PipelineDocumentInput) -> Any:
        participants: list[Any] = []
        if not self._should_skip_triage(input_data):
            participants.append(self.agents["triage"])
        participants.append(self.agents["extractor"])
        if not self._should_skip_coherence(input_data):
            participants.append(self.agents["coherence"])
        return build_sequential_workflow(name="albaran-processing", participants=participants)

    async def _run_workflow_for_model(self, workflow: Any, payload: Any, model_type: type[T]) -> T | None:
        ensure_workflow_available(workflow)
        run_result = workflow.run(payload, stream=True)

        if hasattr(run_result, "__aiter__"):
            latest_match: T | None = None
            async for event in run_result:
                latest_match = coerce_model(model_type, event_payload(event)) or latest_match
            return latest_match

        resolved = await run_result if inspect.isawaitable(run_result) else run_result
        return coerce_model(model_type, resolved)

    async def run(self, input_data: PipelineDocumentInput | dict[str, Any]) -> PipelineRunResult:
        normalized_input = input_data
        if not isinstance(input_data, PipelineDocumentInput):
            normalized_input = PipelineDocumentInput.model_validate(input_data)

        skipped_steps: list[str] = []
        triage_result: TriageResult | None = None
        if self._should_skip_triage(normalized_input):
            skipped_steps.append("triage")
        else:
            triage_workflow = build_sequential_workflow(name="albaran-triage", participants=[self.agents["triage"]])
            triage_payload = normalized_input.raw_text or normalized_input.document_reference
            triage_result = await self._run_workflow_for_model(triage_workflow, triage_payload, TriageResult)
            if triage_result is not None and triage_result.routing_decision != "extract":
                return PipelineRunResult(
                    triage=triage_result,
                    routing_decision=triage_result.routing_decision,
                    skipped_steps=skipped_steps + ["extractor", "coherence"],
                )

        extraction_workflow = build_sequential_workflow(
            name="albaran-extraction", participants=[self.agents["extractor"]]
        )
        extraction_payload = (
            normalized_input.ocr_payload or normalized_input.raw_text or normalized_input.document_reference
        )
        extraction_result = await self._run_workflow_for_model(
            extraction_workflow, extraction_payload, AlbaranExtraction
        )

        if self._should_skip_coherence(normalized_input):
            skipped_steps.append("coherence")
            return PipelineRunResult(
                triage=triage_result,
                extraction=extraction_result,
                routing_decision="extract",
                skipped_steps=skipped_steps,
            )

        coherence_workflow = build_sequential_workflow(
            name="albaran-coherence", participants=[self.agents["coherence"]]
        )
        coherence_payload: Any = (
            extraction_result.model_dump(mode="json") if extraction_result is not None else extraction_payload
        )
        coherence_result = await self._run_workflow_for_model(
            coherence_workflow, coherence_payload, CoherenceCheckResult
        )
        routing_decision = triage_result.routing_decision if triage_result is not None else "extract"
        return PipelineRunResult(
            triage=triage_result,
            extraction=extraction_result,
            coherence=coherence_result,
            routing_decision=routing_decision,
            skipped_steps=skipped_steps,
        )


def build_pipeline(
    client: Any,
    config: AgentsConfig | None = None,
    *,
    tool_registry: ToolRegistry | None = None,
    agents: Mapping[str, Any] | None = None,
) -> AlbaranPipeline:
    return AlbaranPipeline(client, config=config, tool_registry=tool_registry, agents=agents)
