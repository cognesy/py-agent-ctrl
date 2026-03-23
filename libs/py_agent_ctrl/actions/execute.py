from __future__ import annotations

from py_agent_ctrl.api.contracts import AgentBridge
from py_agent_ctrl.api.models import AgentRequest, AgentResponse


def execute_request(bridge: AgentBridge, request: AgentRequest) -> AgentResponse:
    return bridge.execute(request)
