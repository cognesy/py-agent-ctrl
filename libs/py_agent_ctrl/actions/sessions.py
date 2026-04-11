from __future__ import annotations

from py_agent_ctrl.api.models import (
    AgentRequest,
    AgentResponse,
    AgentType,
    BridgeCapabilities,
    SessionCapabilities,
    SessionInfo,
    SessionOperation,
)
from py_agent_ctrl.services.core.errors import UnsupportedSessionOperationError


def with_resume(request: AgentRequest, session_id: str) -> AgentRequest:
    return request.model_copy(update={"resume_session_id": session_id, "continue_session": False})


def with_continue(request: AgentRequest) -> AgentRequest:
    return request.model_copy(update={"continue_session": True, "resume_session_id": None})


def capabilities_from_bridge(capabilities: BridgeCapabilities) -> SessionCapabilities:
    return SessionCapabilities(
        can_resume=capabilities.supports_session_resume,
        can_continue=capabilities.supports_continue,
    )


def require_session_operation(
    agent_type: AgentType,
    capabilities: SessionCapabilities,
    operation: SessionOperation,
) -> None:
    supported = {
        SessionOperation.RESUME: capabilities.can_resume,
        SessionOperation.CONTINUE: capabilities.can_continue,
        SessionOperation.LIST: capabilities.can_list,
        SessionOperation.LOAD: capabilities.can_load,
        SessionOperation.FORK: capabilities.can_fork,
        SessionOperation.TAG: capabilities.can_tag,
        SessionOperation.RENAME: capabilities.can_rename,
        SessionOperation.DELETE: capabilities.can_delete,
    }[operation]
    if not supported:
        raise UnsupportedSessionOperationError(agent_type.value, operation.value)


def session_info_from_response(response: AgentResponse) -> SessionInfo | None:
    if response.session_id is None:
        return None
    return SessionInfo(
        agent_type=response.agent_type,
        session_id=response.session_id,
        execution_id=response.execution_id,
        raw=response.raw_response,
    )
