"""
MAF v1.0 orchestration PoC.

Demonstrates two orchestration patterns from agent_framework:
  1. SequentialBuilder — linear pipeline (Extractor step)
  2. HandoffBuilder   — conditional routing (Validator → Inventory or HITL)

Also sets up OpenTelemetry with console exporter for local testing.
"""


from agent_framework.orchestrations import HandoffBuilder, SequentialBuilder
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)

from .stub_agents import create_extractor, create_inventory, create_validator


def _resolve_workflow_output(data) -> str:
    text = getattr(data, "text", None)
    if text is not None:
        return str(text)
    if hasattr(data, "messages"):
        return str(data.messages[-1].content) if data.messages else str(data)
    return str(data)


# ---------------------------------------------------------------------------
# Telemetry setup (console exporter for local dev)
# ---------------------------------------------------------------------------

def setup_telemetry() -> trace.Tracer:
    """Configure OpenTelemetry with console exporter and return a tracer."""
    resource = Resource.create({"service.name": "maf-poc-albaran"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("maf_poc")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

async def run_extraction_pipeline(client, input_text: str, tracer: trace.Tracer) -> str:
    """
    Stage 1 — SequentialBuilder with a single Extractor agent.

    In production this would be a multi-step pipeline (OCR → normalisation → enrichment).
    Here we use a single agent to validate the SequentialBuilder API.
    """
    extractor = create_extractor(client)

    workflow = SequentialBuilder(
        participants=[extractor],
    ).build()

    with tracer.start_as_current_span("extraction_pipeline") as span:
        span.set_attribute("input.text", input_text)

        result = ""
        async for event in workflow.run(input_text, stream=True):
            if event.type == "output":
                data = getattr(event, "data", event)
                result = _resolve_workflow_output(data)
                span.set_attribute("extraction.result_length", len(result))

    return result


async def run_validation_handoff(client, extracted_json: str, tracer: trace.Tracer) -> dict:
    """
    Stage 2 — HandoffBuilder with Validator → Inventory (or → user for HITL).

    Demonstrates:
      - HandoffBuilder with start agent
      - Conditional routing via agent instructions (coincide → Inventory, discrepancia → user)
      - HITL pause when agent hands off to 'user'
    """
    validator = create_validator(client)
    inventory = create_inventory(client)

    workflow = (
        HandoffBuilder(
            name="validation_handoff",
            participants=[validator, inventory],
        )
        .with_start_agent(validator)
        .build()
    )

    with tracer.start_as_current_span("validation_handoff") as span:
        span.set_attribute("extracted.json_length", len(extracted_json))

        messages = []
        async for event in workflow.run(
            f"Validate this delivery note extraction and process it:\n{extracted_json}",
            stream=True,
        ):
            if event.type == "output":
                data = getattr(event, "data", event)
                messages.append(_resolve_workflow_output(data))
                author = getattr(data, "author_name", "unknown")
                if author == "unknown" and hasattr(data, "messages") and data.messages:
                    author = getattr(data.messages[-1], "author_name", "unknown")
                span.add_event("agent_output", {"agent": author})

        # Determine outcome
        output_text = " ".join(messages)
        if "REC-" in output_text or "posted" in output_text.lower():
            outcome = "posted"
        elif "discrepancia" in output_text.lower() or "discrepancy" in output_text.lower():
            outcome = "hitl_required"
        else:
            outcome = "unknown"

        span.set_attribute("outcome", outcome)

    return {
        "outcome": outcome,
        "messages": messages,
    }


async def run_full_poc(client, albaran_input: str) -> dict:
    """
    Run the full PoC: extraction pipeline → validation handoff.

    Returns a dict with extraction_result, validation_outcome, and all messages.
    """
    tracer = setup_telemetry()

    with tracer.start_as_current_span("full_poc_run") as root_span:
        root_span.set_attribute("albaran.input", albaran_input)

        # Stage 1: Extract
        extracted = await run_extraction_pipeline(client, albaran_input, tracer)
        root_span.set_attribute("extraction.complete", True)

        # Stage 2: Validate + post
        validation_result = await run_validation_handoff(client, extracted, tracer)
        root_span.set_attribute("validation.outcome", validation_result["outcome"])

    return {
        "extraction_result": extracted,
        "validation_outcome": validation_result["outcome"],
        "messages": validation_result["messages"],
    }
