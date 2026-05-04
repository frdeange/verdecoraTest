from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class StructuredAgentStub:
    def __init__(self, *, structured_output: type[BaseModel], kwargs: dict[str, Any]) -> None:
        self.structured_output = structured_output
        self.kwargs = kwargs

    def decode(self, payload: str | dict[str, Any] | BaseModel) -> BaseModel:
        if isinstance(payload, self.structured_output):
            return payload
        if isinstance(payload, str):
            return self.structured_output.model_validate_json(payload)
        return self.structured_output.model_validate(payload)


def build_structured_agent_stub(**kwargs: Any) -> StructuredAgentStub:
    return StructuredAgentStub(structured_output=kwargs["structured_output"], kwargs=dict(kwargs))
