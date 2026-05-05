from __future__ import annotations

from typing import Any, Mapping

from agent_framework.orchestrations import SequentialBuilder
from azure.identity.aio import DefaultAzureCredential
from pydantic import BaseModel, Field, ValidationError

from src.config.agents import AgentsConfig, get_agents_config
from src.models.albaran import AlbaranExtraction, CoherenceCheckResult, TriageResult
from src.models.inventory import PostingResult
from src.models.validation import ValidationResult

from .factory import ToolRegistry, create_agents, create_clients
from .security import sanitize_untrusted_payload


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
    validation: ValidationResult | None = None
    inventory: PostingResult | None = None
    routing_decision: str
    skipped_steps: list[str] = Field(default_factory=list)


class AlbaranPipeline:
    """Sequential pipeline: Triage → Extractor → Coherence → Validator → Inventory."""

    def __init__(
        self,
        config: AgentsConfig | None = None,
        *,
        project_endpoint: str | None = None,
        credential: DefaultAzureCredential | Any | None = None,
        gpt5_client: Any | None = None,
        gpt5_mini_client: Any | None = None,
        mcp_tools: ToolRegistry | None = None,
        agents: Mapping[str, Any] | None = None,
    ) -> None:
        self.config = config or get_agents_config()
        self.project_endpoint = project_endpoint or self.config.endpoints.azure_ai_project_endpoint
        self.credential = credential or self.config.create_credential()
        self.gpt5_client = gpt5_client
        self.gpt5_mini_client = gpt5_mini_client

        if agents is None:
            if self.gpt5_client is None or self.gpt5_mini_client is None:
                self.gpt5_client, self.gpt5_mini_client = create_clients(self.project_endpoint, self.credential)
            self.agents = create_agents(self.gpt5_client, self.gpt5_mini_client, mcp_tools=mcp_tools)
        else:
            self.agents = dict(agents)

        self.communication_agent = self.agents.get("communication")

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

    def build_workflow(self, *, skip_triage: bool = False, skip_coherence: bool = False) -> Any:
        participants: list[Any] = []
        if not skip_triage:
            participants.append(self.agents["triage"])
        participants.append(self.agents["extractor"])
        if not skip_coherence:
            participants.extend([self.agents["coherence"], self.agents["validator"], self.agents["inventory"]])
        return SequentialBuilder(participants=participants).build()

    def _build_stage_workflow(self, stage: str) -> Any:
        return SequentialBuilder(participants=[self.agents[stage]]).build()

    async def _run_workflow(self, workflow: Any, payload: Any) -> Any:
        run_result = workflow.run(payload)
        resolved = await run_result if hasattr(run_result, "__await__") else run_result
        if hasattr(resolved, "__aiter__"):
            latest_payload: Any = None
            async for event in resolved:
                data = getattr(event, "data", event)
                text = getattr(data, "text", None)
                if text is not None:
                    latest_payload = text
                elif hasattr(data, "messages"):
                    latest_payload = data.messages[-1].content if data.messages else str(data)
                else:
                    latest_payload = data
            return latest_payload
        return getattr(resolved, "text", resolved)

    def _coerce_model(self, model_type: type[Any], payload: Any) -> Any:
        if payload is None:
            return None
        if isinstance(payload, model_type):
            return payload
        try:
            if isinstance(payload, str):
                return model_type.model_validate_json(payload)
            return model_type.model_validate(payload)
        except (TypeError, ValueError, ValidationError):
            return None

    def _sanitize_input(self, input_data: PipelineDocumentInput) -> PipelineDocumentInput:
        sanitized_raw_text = sanitize_untrusted_payload(input_data.raw_text)
        sanitized_ocr_payload = sanitize_untrusted_payload(input_data.ocr_payload)
        sanitized_supplier_id = sanitize_untrusted_payload(input_data.supplier_id)
        sanitized_supplier_hint = sanitize_untrusted_payload(input_data.supplier_hint)
        sanitized_metadata = sanitize_untrusted_payload(input_data.metadata)

        if (
            sanitized_raw_text == input_data.raw_text
            and sanitized_ocr_payload == input_data.ocr_payload
            and sanitized_supplier_id == input_data.supplier_id
            and sanitized_supplier_hint == input_data.supplier_hint
            and sanitized_metadata == input_data.metadata
        ):
            return input_data

        metadata = dict(sanitized_metadata)
        metadata["input_sanitized"] = True
        return input_data.model_copy(
            update={
                "raw_text": sanitized_raw_text,
                "ocr_payload": sanitized_ocr_payload,
                "supplier_id": sanitized_supplier_id,
                "supplier_hint": sanitized_supplier_hint,
                "metadata": metadata,
            }
        )

    async def run(self, input_data: PipelineDocumentInput | dict[str, Any]) -> PipelineRunResult:
        normalized_input = input_data
        if not isinstance(input_data, PipelineDocumentInput):
            normalized_input = PipelineDocumentInput.model_validate(input_data)
        normalized_input = self._sanitize_input(normalized_input)

        skipped_steps: list[str] = []
        triage_result: TriageResult | None = None
        if self._should_skip_triage(normalized_input):
            skipped_steps.append("triage")
        else:
            triage_payload = normalized_input.raw_text or normalized_input.document_reference
            triage_output = await self._run_workflow(self._build_stage_workflow("triage"), triage_payload)
            triage_result = self._coerce_model(TriageResult, triage_output)
            if triage_result is not None and triage_result.routing_decision != "extract":
                return PipelineRunResult(
                    triage=triage_result,
                    routing_decision=triage_result.routing_decision,
                    skipped_steps=skipped_steps + ["extractor", "coherence", "validation", "inventory"],
                )

        extraction_payload = (
            normalized_input.ocr_payload or normalized_input.raw_text or normalized_input.document_reference
        )
        extraction_output = await self._run_workflow(self._build_stage_workflow("extractor"), extraction_payload)
        extraction_result = self._coerce_model(AlbaranExtraction, extraction_output)

        if self._should_skip_coherence(normalized_input):
            skipped_steps.extend(["coherence", "validation", "inventory"])
            return PipelineRunResult(
                triage=triage_result,
                extraction=extraction_result,
                routing_decision="extract",
                skipped_steps=skipped_steps,
            )

        coherence_payload: Any = (
            extraction_result.model_dump(mode="json") if extraction_result is not None else extraction_payload
        )
        coherence_output = await self._run_workflow(self._build_stage_workflow("coherence"), coherence_payload)
        coherence_result = self._coerce_model(CoherenceCheckResult, coherence_output)

        validation_payload = {
            "extraction": extraction_result.model_dump(mode="json") if extraction_result is not None else None,
            "coherence": coherence_result.model_dump(mode="json") if coherence_result is not None else None,
        }
        validation_output = await self._run_workflow(self._build_stage_workflow("validator"), validation_payload)
        validation_result = self._coerce_model(ValidationResult, validation_output)

        if validation_result is None or validation_result.recommendation != "approve":
            skipped_steps.append("inventory")
            routing_decision = validation_result.recommendation if validation_result is not None else "hitl_review"
            return PipelineRunResult(
                triage=triage_result,
                extraction=extraction_result,
                coherence=coherence_result,
                validation=validation_result,
                routing_decision=routing_decision,
                skipped_steps=skipped_steps,
            )

        inventory_payload = {
            "validation": validation_result.model_dump(mode="json"),
            "extraction": extraction_result.model_dump(mode="json") if extraction_result is not None else None,
        }
        inventory_output = await self._run_workflow(self._build_stage_workflow("inventory"), inventory_payload)
        inventory_result = self._coerce_model(PostingResult, inventory_output)
        routing_decision = "posted" if inventory_result is not None and inventory_result.success else "hitl_review"
        return PipelineRunResult(
            triage=triage_result,
            extraction=extraction_result,
            coherence=coherence_result,
            validation=validation_result,
            inventory=inventory_result,
            routing_decision=routing_decision,
            skipped_steps=skipped_steps,
        )


__all__ = ["AlbaranPipeline", "PipelineDocumentInput", "PipelineRunResult"]
