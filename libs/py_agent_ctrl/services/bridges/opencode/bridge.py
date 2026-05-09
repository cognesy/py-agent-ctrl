from __future__ import annotations

from py_agent_ctrl.api.events import StreamResult
from py_agent_ctrl.api.models import AgentRequest, AgentResponse, AgentType, BridgeCapabilities
from py_agent_ctrl.services.bridges.opencode.command_builder import build_opencode_command
from py_agent_ctrl.services.bridges.opencode.parser import opencode_response_from_output, parse_opencode_events
from py_agent_ctrl.services.core.env import agent_env
from py_agent_ctrl.services.core.parsing import (
    FunctionEventParser,
    FunctionResponseReducer,
)
from py_agent_ctrl.services.core.paths import normalize_request_paths
from py_agent_ctrl.services.core.pipeline import ProviderExecutionPipeline
from py_agent_ctrl.services.core.subprocess import (
    CommandSpec,
    run_command,
)

_OPENCODE_EVENT_PARSER = FunctionEventParser(AgentType.OPENCODE, parse_opencode_events)
_OPENCODE_RESPONSE_REDUCER = FunctionResponseReducer(AgentType.OPENCODE, opencode_response_from_output)
_OPENCODE_PIPELINE = ProviderExecutionPipeline(_OPENCODE_EVENT_PARSER, _OPENCODE_RESPONSE_REDUCER)


class OpenCodeBridge:
    def capabilities(self) -> BridgeCapabilities:
        return BridgeCapabilities(
            agent_type=AgentType.OPENCODE,
            cli_name="opencode",
            supports_tool_events=True,
            supports_usage=True,
            supports_reasoning=False,
            supports_plan_events=False,
            supports_file_change_events=False,
            supports_permission_callbacks=False,
            supports_cancellation=False,
            supports_structured_json_output=True,
            supported_options=[
                "model",
                "agent",
                "files",
                "title",
                "share_session",
                "resume_session_id",
                "continue_session",
            ],
        )

    def execute(self, request: AgentRequest) -> AgentResponse:
        request = normalize_request_paths(request)
        command = CommandSpec(
            argv=build_opencode_command(request),
            cwd=request.working_directory,
            env=agent_env(AgentType.OPENCODE, request.provider_options),
            timeout_seconds=request.timeout_seconds,
        )
        output = run_command(command)
        return _OPENCODE_PIPELINE.parse_output(output)

    def stream(self, request: AgentRequest) -> StreamResult:
        request = normalize_request_paths(request)
        command = CommandSpec(
            argv=build_opencode_command(request),
            cwd=request.working_directory,
            env=agent_env(AgentType.OPENCODE, request.provider_options),
            timeout_seconds=request.timeout_seconds,
        )
        return _OPENCODE_PIPELINE.stream_command(command)
