from __future__ import annotations

from typing import Protocol

from py_agent_ctrl.api.events import StreamResult
from py_agent_ctrl.api.models import AgentRequest, AgentResponse, BridgeCapabilities


class AgentBridge(Protocol):
    def capabilities(self) -> BridgeCapabilities: ...

    def execute(self, request: AgentRequest) -> AgentResponse: ...

    def stream(self, request: AgentRequest) -> StreamResult: ...
