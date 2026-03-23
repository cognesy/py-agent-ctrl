from __future__ import annotations

from py_agent_ctrl.api.models import AgentRequest


def with_resume(request: AgentRequest, session_id: str) -> AgentRequest:
    return request.model_copy(update={"resume_session_id": session_id, "continue_session": False})


def with_continue(request: AgentRequest) -> AgentRequest:
    return request.model_copy(update={"continue_session": True, "resume_session_id": None})
