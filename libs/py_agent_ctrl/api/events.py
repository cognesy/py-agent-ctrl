from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, Literal

from pydantic import BaseModel, Field

from py_agent_ctrl.api.models import TokenUsage, ToolCall


class StreamDiagnostics(BaseModel):
    parse_failures: int = 0
    skipped_non_json_lines: int = 0
    overlong_lines: int = 0
    parse_failure_samples: list[str] = Field(default_factory=list)
    stderr_tail: str = ""
    timed_out: bool = False
    duration_ms: int | None = None
    command_preview: list[str] = Field(default_factory=list)
    cwd: str | None = None
    error_type: str | None = None


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


class AgentReasoningEvent(BaseModel):
    type: Literal["reasoning"] = "reasoning"
    text: str = ""
    raw: dict[str, Any] | None = None


class AgentPlanUpdateEvent(BaseModel):
    type: Literal["plan_update"] = "plan_update"
    plan: Any = None
    raw: dict[str, Any] | None = None


class AgentUsageEvent(BaseModel):
    type: Literal["usage"] = "usage"
    usage: TokenUsage
    raw: dict[str, Any] | None = None


class AgentWarningEvent(BaseModel):
    type: Literal["warning"] = "warning"
    message: str
    raw: dict[str, Any] | None = None


class AgentFileChangeEvent(BaseModel):
    type: Literal["file_change"] = "file_change"
    path: str | None = None
    action: str | None = None
    diff: str | None = None
    raw: dict[str, Any] | None = None


class AgentUnknownEvent(BaseModel):
    type: Literal["unknown"] = "unknown"
    raw: dict[str, Any] = Field(default_factory=dict)


AgentEvent = (
    AgentTextEvent
    | AgentToolCallEvent
    | AgentResultEvent
    | AgentReasoningEvent
    | AgentPlanUpdateEvent
    | AgentUsageEvent
    | AgentWarningEvent
    | AgentFileChangeEvent
    | AgentUnknownEvent
)


class StreamResult:
    """Iterable stream of agent events that exposes the subprocess exit code after exhaustion."""

    def __init__(
        self,
        events: Iterator[AgentEvent],
        exit_code_getter: Callable[[], int],
        diagnostics_getter: Callable[[], StreamDiagnostics] | None = None,
    ) -> None:
        self._events = events
        self._exit_code_getter = exit_code_getter
        self._diagnostics_getter = diagnostics_getter or StreamDiagnostics

    def __iter__(self) -> Iterator[AgentEvent]:
        yield from self._events

    @property
    def exit_code(self) -> int:
        return self._exit_code_getter()

    @property
    def diagnostics(self) -> StreamDiagnostics:
        return self._diagnostics_getter()
