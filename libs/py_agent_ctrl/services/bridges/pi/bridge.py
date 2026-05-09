from __future__ import annotations

from py_agent_ctrl.api.events import StreamResult
from py_agent_ctrl.api.models import AgentRequest, AgentResponse, AgentType, BridgeCapabilities
from py_agent_ctrl.services.bridges.pi.command_builder import build_pi_command
from py_agent_ctrl.services.bridges.pi.parser import parse_pi_events, pi_response_from_output
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

_PI_EVENT_PARSER = FunctionEventParser(AgentType.PI, parse_pi_events)
_PI_RESPONSE_REDUCER = FunctionResponseReducer(AgentType.PI, pi_response_from_output)
_PI_PIPELINE = ProviderExecutionPipeline(_PI_EVENT_PARSER, _PI_RESPONSE_REDUCER)


class PiBridge:
    def capabilities(self) -> BridgeCapabilities:
        return BridgeCapabilities(
            agent_type=AgentType.PI,
            cli_name="pi",
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
                "provider",
                "thinking",
                "tools",
                "files",
                "extensions",
                "skills",
                "session_dir",
            ],
        )

    def execute(self, request: AgentRequest) -> AgentResponse:
        request = normalize_request_paths(request)
        command = CommandSpec(
            argv=build_pi_command(request),
            cwd=request.working_directory,
            env=agent_env(AgentType.PI, request.provider_options),
            timeout_seconds=request.timeout_seconds,
        )
        output = run_command(command)
        return _PI_PIPELINE.parse_output(output)

    def stream(self, request: AgentRequest) -> StreamResult:
        request = normalize_request_paths(request)
        command = CommandSpec(
            argv=build_pi_command(request),
            cwd=request.working_directory,
            env=agent_env(AgentType.PI, request.provider_options),
            timeout_seconds=request.timeout_seconds,
        )
        return _PI_PIPELINE.stream_command(command)
