from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel


class StructuredAgentStub:
    def __init__(self, *, response_format: type[BaseModel], kwargs: dict[str, Any]) -> None:
        self.response_format = response_format
        self.kwargs = kwargs

    def decode(self, payload: str | dict[str, Any] | BaseModel) -> BaseModel:
        if isinstance(payload, self.response_format):
            return payload
        if isinstance(payload, str):
            return self.response_format.model_validate_json(payload)
        return self.response_format.model_validate(payload)


class WorkflowResult:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeEvent:
    def __init__(self, data: Any) -> None:
        self.data = data


class FakeAsyncStream:
    def __init__(self, events: list[Any]) -> None:
        self._events = iter(events)

    def __aiter__(self) -> AsyncIterator[Any]:
        return self

    async def __anext__(self) -> Any:
        try:
            return next(self._events)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FakeWorkflow:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.payloads: list[Any] = []

    def run(self, payload: Any) -> Any:
        self.payloads.append(payload)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def build_structured_agent_stub(*args: Any, **kwargs: Any) -> StructuredAgentStub:
    response_format = kwargs.get("response_format")
    if response_format is None:
        response_format = kwargs.get("default_options", {}).get("response_format")
    if response_format is None:
        raise KeyError("response_format")

    captured_kwargs = dict(kwargs)
    if args:
        captured_kwargs["client"] = args[0]
    return StructuredAgentStub(response_format=response_format, kwargs=captured_kwargs)
