from __future__ import annotations

from pathlib import Path
from typing import Any, Self

from py_agent_ctrl.actions.execute import execute_request
from py_agent_ctrl.actions.stream import stream_request
from py_agent_ctrl.api.contracts import AgentBridge
from py_agent_ctrl.api.events import StreamResult
from py_agent_ctrl.api.models import AgentRequest, AgentResponse, BridgeCapabilities


class BaseAgentAction:
    def __init__(self, bridge: AgentBridge, *, request: AgentRequest | None = None) -> None:
        self._bridge = bridge
        self._request = request or AgentRequest(prompt="")

    def _copy(self, **updates: Any) -> Self:
        return self.__class__(
            self._bridge,
            request=self._request.model_copy(update=updates),
        )

    def _with_provider_option(self, key: str, value: Any) -> Self:
        provider_options = dict(self._request.provider_options)
        provider_options[key] = value
        return self._copy(provider_options=provider_options)

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

    def resume_session(self, session_id: str) -> Self:
        return self._copy(resume_session_id=session_id, continue_session=False)

    def continue_session(self) -> Self:
        return self._copy(continue_session=True, resume_session_id=None)

    def capabilities(self) -> BridgeCapabilities:
        return self._bridge.capabilities()

    def execute(self, prompt: str) -> AgentResponse:
        return execute_request(self._bridge, self._request.model_copy(update={"prompt": prompt}))

    def stream(self, prompt: str) -> StreamResult:
        return stream_request(self._bridge, self._request.model_copy(update={"prompt": prompt}))
