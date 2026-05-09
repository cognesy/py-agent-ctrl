from __future__ import annotations

from py_agent_ctrl.api.events import StreamResult
from py_agent_ctrl.api.models import AgentRequest, AgentResponse, AgentType, BridgeCapabilities
from py_agent_ctrl.services.bridges.claude_code.command_builder import build_claude_command
from py_agent_ctrl.services.bridges.claude_code.parser import events_to_response, parse_claude_events
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

_CLAUDE_EVENT_PARSER = FunctionEventParser(AgentType.CLAUDE_CODE, parse_claude_events)
_CLAUDE_RESPONSE_REDUCER = FunctionResponseReducer(AgentType.CLAUDE_CODE, events_to_response)
_CLAUDE_PIPELINE = ProviderExecutionPipeline(_CLAUDE_EVENT_PARSER, _CLAUDE_RESPONSE_REDUCER)


class ClaudeCodeBridge:
    def capabilities(self) -> BridgeCapabilities:
        return BridgeCapabilities(
            agent_type=AgentType.CLAUDE_CODE,
            cli_name="claude",
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
                "system_prompt",
                "append_system_prompt",
                "max_turns",
                "permission_mode",
                "allowed_tools",
                "resume_session_id",
                "continue_session",
                "additional_directories",
            ],
        )

    def execute(self, request: AgentRequest) -> AgentResponse:
        request = normalize_request_paths(request)
        command = CommandSpec(
            argv=build_claude_command(request),
            cwd=request.working_directory,
            env=agent_env(AgentType.CLAUDE_CODE, request.provider_options),
            timeout_seconds=request.timeout_seconds,
        )
        output = run_command(command)
        return _CLAUDE_PIPELINE.parse_output(output)

    def stream(self, request: AgentRequest) -> StreamResult:
        request = normalize_request_paths(request)
        command = CommandSpec(
            argv=build_claude_command(request),
            cwd=request.working_directory,
            env=agent_env(AgentType.CLAUDE_CODE, request.provider_options),
            timeout_seconds=request.timeout_seconds,
        )
        return _CLAUDE_PIPELINE.stream_command(command)
