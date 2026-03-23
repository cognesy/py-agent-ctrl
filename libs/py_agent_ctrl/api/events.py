from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, Literal

from pydantic import BaseModel, Field

from py_agent_ctrl.api.models import ToolCall


class AgentTextEvent(BaseModel):
    type: Literal["text"] = "text"
    text: str
    raw: dict[str, Any] | None = None


class AgentToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool_call: ToolCall
    raw: dict[str, Any] | None = None


class AgentResultEvent(BaseModel):
    type: Literal["result"] = "result"
    session_id: str | None = None
    cost_usd: float | None = None
    duration_ms: int | None = None
    raw: dict[str, Any] | None = None


class AgentUnknownEvent(BaseModel):
    type: Literal["unknown"] = "unknown"
    raw: dict[str, Any] = Field(default_factory=dict)


AgentEvent = AgentTextEvent | AgentToolCallEvent | AgentResultEvent | AgentUnknownEvent


class StreamResult:
    """Iterable stream of agent events that exposes the subprocess exit code after exhaustion."""

    def __init__(
        self,
        events: Iterator[AgentEvent],
        exit_code_getter: Callable[[], int],
    ) -> None:
        self._events = events
        self._exit_code_getter = exit_code_getter

    def __iter__(self) -> Iterator[AgentEvent]:
        yield from self._events

    @property
    def exit_code(self) -> int:
        return self._exit_code_getter()
