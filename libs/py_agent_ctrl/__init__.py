from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__ = _pkg_version("py-agent-ctrl")
except PackageNotFoundError:
    __version__ = "0.0.0"

from py_agent_ctrl.api.events import (
    AgentEvent,
    AgentResultEvent,
    AgentTextEvent,
    AgentToolCallEvent,
    AgentUnknownEvent,
    StreamResult,
)
from py_agent_ctrl.api.facade import AgentCtrl
from py_agent_ctrl.api.models import (
    AgentRequest,
    AgentResponse,
    AgentType,
    BridgeCapabilities,
    TokenUsage,
    ToolCall,
)
from py_agent_ctrl.services.core.errors import AgentError, BinaryNotFoundError

__all__ = [
    "AgentCtrl",
    "AgentError",
    "AgentEvent",
    "AgentRequest",
    "AgentResponse",
    "AgentResultEvent",
    "AgentTextEvent",
    "AgentToolCallEvent",
    "AgentType",
    "AgentUnknownEvent",
    "BinaryNotFoundError",
    "BridgeCapabilities",
    "StreamResult",
    "TokenUsage",
    "ToolCall",
]
