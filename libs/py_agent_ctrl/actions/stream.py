from __future__ import annotations

from py_agent_ctrl.api.contracts import AgentBridge
from py_agent_ctrl.api.events import StreamResult
from py_agent_ctrl.api.models import AgentRequest


def stream_request(bridge: AgentBridge, request: AgentRequest) -> StreamResult:
    return bridge.stream(request)
