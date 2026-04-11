from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Self

from py_agent_ctrl.actions.execute import execute_request
from py_agent_ctrl.actions.stream import stream_request
from py_agent_ctrl.api.contracts import AgentBridge
from py_agent_ctrl.api.events import AgentEvent, AgentTextEvent, AgentToolCallEvent, StreamResult
from py_agent_ctrl.api.models import AgentRequest, AgentResponse, BridgeCapabilities, SandboxDriver, ToolCall


@dataclass(frozen=True)
class ActionCallbacks:
    text: tuple[Callable[[str], None], ...] = field(default_factory=tuple)
    tool_call: tuple[Callable[[ToolCall], None], ...] = field(default_factory=tuple)
    event: tuple[Callable[[AgentEvent], None], ...] = field(default_factory=tuple)
    complete: tuple[Callable[[AgentResponse], None], ...] = field(default_factory=tuple)
    error: tuple[Callable[[Exception], None], ...] = field(default_factory=tuple)


class BaseAgentAction:
    def __init__(
        self,
        bridge: AgentBridge,
        *,
        request: AgentRequest | None = None,
        callbacks: ActionCallbacks | None = None,
    ) -> None:
        self._bridge = bridge
        self._request = request or AgentRequest(prompt="")
        self._callbacks = callbacks or ActionCallbacks()

    def _copy(self, **updates: Any) -> Self:
        return self.__class__(
            self._bridge,
            request=self._request.model_copy(update=updates),
            callbacks=self._callbacks,
        )

    def _with_provider_option(self, key: str, value: Any) -> Self:
        provider_options = dict(self._request.provider_options)
        provider_options[key] = value
        return self._copy(provider_options=provider_options)

    def _copy_with_callbacks(self, callbacks: ActionCallbacks) -> Self:
        return self.__class__(
            self._bridge,
            request=self._request,
            callbacks=callbacks,
        )

    def _handle_error(self, error: Exception) -> None:
        for error_callback in self._callbacks.error:
            error_callback(error)

    def _emit_event_callbacks(self, event: AgentEvent) -> None:
        for event_callback in self._callbacks.event:
            event_callback(event)
        if isinstance(event, AgentTextEvent):
            for text_callback in self._callbacks.text:
                text_callback(event.text)
        elif isinstance(event, AgentToolCallEvent):
            for tool_call_callback in self._callbacks.tool_call:
                tool_call_callback(event.tool_call)

    def _emit_response_callbacks(self, response: AgentResponse) -> None:
        if response.text:
            for text_callback in self._callbacks.text:
                text_callback(response.text)
        for tool_call in response.tool_calls:
            for tool_call_callback in self._callbacks.tool_call:
                tool_call_callback(tool_call)
        for complete_callback in self._callbacks.complete:
            complete_callback(response)

    def _emit_stream_event_callbacks(self, event: AgentEvent, text_state: str) -> str:
        for event_callback in self._callbacks.event:
            event_callback(event)
        if isinstance(event, AgentTextEvent):
            return self._emit_stream_text_callbacks(event.text, text_state)
        if isinstance(event, AgentToolCallEvent):
            for tool_call_callback in self._callbacks.tool_call:
                tool_call_callback(event.tool_call)
        return text_state

    def _emit_stream_text_callbacks(self, text: str, text_state: str) -> str:
        if _is_internal_event_json(text):
            return text_state
        next_state, delta = _dedupe_text_delta(text_state, text)
        if delta:
            for text_callback in self._callbacks.text:
                text_callback(delta)
        return next_state

    def with_model(self, model: str) -> Self:
        return self._copy(model=model)

    def with_system_prompt(self, prompt: str) -> Self:
        return self._copy(system_prompt=prompt)

    def append_system_prompt(self, prompt: str) -> Self:
        return self._copy(append_system_prompt=prompt)

    def with_max_turns(self, turns: int) -> Self:
        return self._copy(max_turns=max(1, turns))

    def in_directory(self, path: str | Path) -> Self:
        return self._copy(working_directory=str(path))

    def with_additional_dirs(self, directories: list[str]) -> Self:
        return self._copy(additional_directories=list(directories))

    def with_timeout(self, seconds: int) -> Self:
        return self._copy(timeout_seconds=seconds)

    def with_sandbox_driver(self, driver: SandboxDriver | str) -> Self:
        return self._copy(sandbox_driver=SandboxDriver(driver))

    def resume_session(self, session_id: str) -> Self:
        return self._copy(resume_session_id=session_id, continue_session=False)

    def continue_session(self) -> Self:
        return self._copy(continue_session=True, resume_session_id=None)

    def capabilities(self) -> BridgeCapabilities:
        return self._bridge.capabilities()

    def on_text(self, handler: Callable[[str], None]) -> Self:
        return self._copy_with_callbacks(
            ActionCallbacks(
                text=(*self._callbacks.text, handler),
                tool_call=self._callbacks.tool_call,
                event=self._callbacks.event,
                complete=self._callbacks.complete,
                error=self._callbacks.error,
            )
        )

    def on_tool_call(self, handler: Callable[[ToolCall], None]) -> Self:
        return self._copy_with_callbacks(
            ActionCallbacks(
                text=self._callbacks.text,
                tool_call=(*self._callbacks.tool_call, handler),
                event=self._callbacks.event,
                complete=self._callbacks.complete,
                error=self._callbacks.error,
            )
        )

    def on_event(self, handler: Callable[[AgentEvent], None]) -> Self:
        return self._copy_with_callbacks(
            ActionCallbacks(
                text=self._callbacks.text,
                tool_call=self._callbacks.tool_call,
                event=(*self._callbacks.event, handler),
                complete=self._callbacks.complete,
                error=self._callbacks.error,
            )
        )

    def on_complete(self, handler: Callable[[AgentResponse], None]) -> Self:
        return self._copy_with_callbacks(
            ActionCallbacks(
                text=self._callbacks.text,
                tool_call=self._callbacks.tool_call,
                event=self._callbacks.event,
                complete=(*self._callbacks.complete, handler),
                error=self._callbacks.error,
            )
        )

    def on_error(self, handler: Callable[[Exception], None]) -> Self:
        return self._copy_with_callbacks(
            ActionCallbacks(
                text=self._callbacks.text,
                tool_call=self._callbacks.tool_call,
                event=self._callbacks.event,
                complete=self._callbacks.complete,
                error=(*self._callbacks.error, handler),
            )
        )

    def execute(self, prompt: str) -> AgentResponse:
        try:
            response = execute_request(self._bridge, self._request.model_copy(update={"prompt": prompt}))
        except Exception as error:
            self._handle_error(error)
            raise
        self._emit_response_callbacks(response)
        return response

    def stream(self, prompt: str) -> StreamResult:
        result = stream_request(self._bridge, self._request.model_copy(update={"prompt": prompt}))

        def _events() -> Iterator[AgentEvent]:
            text_state = ""
            try:
                for event in result:
                    text_state = self._emit_stream_event_callbacks(event, text_state)
                    yield event
            except Exception as error:
                self._handle_error(error)
                raise

        return StreamResult(_events(), lambda: result.exit_code)


def _dedupe_text_delta(current: str, incoming: str) -> tuple[str, str]:
    if not incoming:
        return current, ""
    if not current:
        return incoming, incoming
    if incoming == current or current.endswith(incoming) or current.startswith(incoming):
        return current, ""
    if incoming.startswith(current):
        return incoming, incoming[len(current) :]
    if incoming.endswith(current):
        return incoming, incoming[: -len(current)]
    overlap = _suffix_prefix_overlap(current, incoming)
    if overlap > 0:
        delta = incoming[overlap:]
        return current + delta, delta
    return current + incoming, incoming


def _suffix_prefix_overlap(left: str, right: str) -> int:
    max_overlap = min(len(left), len(right))
    for length in range(max_overlap, 0, -1):
        if left.endswith(right[:length]):
            return length
    return 0


def _is_internal_event_json(text: str) -> bool:
    stripped = text.strip()
    if not stripped.startswith("{"):
        return False
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return False
    if not isinstance(parsed, dict):
        return False
    if parsed.get("type") == "output" and isinstance(parsed.get("data"), dict):
        data = parsed["data"]
        return "parentUuid" in data and isinstance(data.get("sessionId"), str) and isinstance(data.get("userType"), str)
    return False
