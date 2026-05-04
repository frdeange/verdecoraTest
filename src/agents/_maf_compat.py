from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import ValidationError

try:  # pragma: no cover - exercised only when agent-framework is installed.
    from agent_framework import Agent, AgentBuilder
    from agent_framework.orchestrations import HandoffBuilder, SequentialBuilder
except ImportError as exc:  # pragma: no cover - default in local dev until MAF is installed.
    Agent = None
    AgentBuilder = None
    HandoffBuilder = None
    SequentialBuilder = None
    MAF_IMPORT_ERROR: ImportError | None = exc
else:  # pragma: no cover - depends on optional dependency.
    MAF_IMPORT_ERROR = None

T = TypeVar("T")


@dataclass(slots=True)
class UnavailableAgentSpec:
    name: str
    model: str
    instructions: str
    structured_output: type[Any] | None = None
    tools: tuple[Any, ...] = field(default_factory=tuple)
    handoffs: tuple[str, ...] = field(default_factory=tuple)
    is_available: bool = False
    reason: str = "agent-framework is not installed"


@dataclass(slots=True)
class UnavailableWorkflowSpec:
    name: str
    participants: tuple[Any, ...]
    start_agent: Any | None = None
    is_available: bool = False
    reason: str = "agent-framework is not installed"


def _build_with_builder(
    *,
    client: Any,
    name: str,
    model: str,
    instructions: str,
    structured_output: type[Any] | None,
    resolved_tools: list[Any],
    resolved_handoffs: list[str],
) -> Any:
    builder = AgentBuilder(name=name, model=model)
    if hasattr(builder, "with_instructions"):
        builder = builder.with_instructions(instructions)
    if structured_output is not None and hasattr(builder, "with_structured_output"):
        builder = builder.with_structured_output(structured_output)
    if resolved_tools:
        if hasattr(builder, "with_tools"):
            builder = builder.with_tools(resolved_tools)
        elif hasattr(builder, "with_tool"):
            for tool in resolved_tools:
                builder = builder.with_tool(tool)
    if resolved_handoffs and hasattr(builder, "with_handoffs"):
        builder = builder.with_handoffs(resolved_handoffs)
    return builder.build(client)


def _build_with_agent(
    *,
    client: Any,
    name: str,
    instructions: str,
    structured_output: type[Any] | None,
    resolved_tools: list[Any],
    resolved_handoffs: list[str],
) -> Any:
    agent_kwargs: dict[str, Any] = {
        "client": client,
        "name": name,
        "instructions": instructions,
        "tools": resolved_tools,
    }
    if resolved_handoffs:
        agent_kwargs["handoffs"] = resolved_handoffs
    if structured_output is not None:
        agent_kwargs["structured_output"] = structured_output
    try:
        return Agent(**agent_kwargs)
    except TypeError:
        agent_kwargs.pop("structured_output", None)
        return Agent(**agent_kwargs)


def create_structured_agent(
    *,
    client: Any,
    name: str,
    model: str,
    instructions: str,
    structured_output: type[Any] | None = None,
    tools: list[Any] | None = None,
    handoffs: list[str] | None = None,
) -> Any:
    resolved_tools = list(tools or [])
    resolved_handoffs = list(handoffs or [])

    if AgentBuilder is not None:
        return _build_with_builder(
            client=client,
            name=name,
            model=model,
            instructions=instructions,
            structured_output=structured_output,
            resolved_tools=resolved_tools,
            resolved_handoffs=resolved_handoffs,
        )

    if Agent is not None:
        return _build_with_agent(
            client=client,
            name=name,
            instructions=instructions,
            structured_output=structured_output,
            resolved_tools=resolved_tools,
            resolved_handoffs=resolved_handoffs,
        )

    return UnavailableAgentSpec(
        name=name,
        model=model,
        instructions=instructions,
        structured_output=structured_output,
        tools=tuple(resolved_tools),
        handoffs=tuple(resolved_handoffs),
        reason=str(MAF_IMPORT_ERROR or "agent-framework is not installed"),
    )


def build_sequential_workflow(*, name: str, participants: list[Any]) -> Any:
    if SequentialBuilder is None:
        return UnavailableWorkflowSpec(
            name=name,
            participants=tuple(participants),
            reason=str(MAF_IMPORT_ERROR or "agent-framework is not installed"),
        )

    return SequentialBuilder(participants=participants).build()


def build_handoff_workflow(*, name: str, participants: list[Any], start_agent: Any) -> Any:
    if HandoffBuilder is None:
        return UnavailableWorkflowSpec(
            name=name,
            participants=tuple(participants),
            start_agent=start_agent,
            reason=str(MAF_IMPORT_ERROR or "agent-framework is not installed"),
        )

    return HandoffBuilder(name=name, participants=participants).with_start_agent(start_agent).build()


def ensure_workflow_available(workflow: Any) -> None:
    if isinstance(workflow, UnavailableWorkflowSpec):
        raise RuntimeError(
            f"Cannot run workflow '{workflow.name}': {workflow.reason}. Install the agent-framework package first."
        )


def event_payload(event: Any) -> Any:
    return getattr(event, "data", event)


def coerce_model(model_type: type[T], payload: Any) -> T | None:
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
