from __future__ import annotations

from py_agent_ctrl.api.events import StreamResult
from py_agent_ctrl.api.models import AgentRequest, AgentResponse, AgentType, BridgeCapabilities
from py_agent_ctrl.services.bridges.codex.command_builder import build_codex_command
from py_agent_ctrl.services.bridges.codex.parser import codex_response_from_output, parse_codex_events
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

_CODEX_EVENT_PARSER = FunctionEventParser(AgentType.CODEX, parse_codex_events)
_CODEX_RESPONSE_REDUCER = FunctionResponseReducer(AgentType.CODEX, codex_response_from_output)
_CODEX_PIPELINE = ProviderExecutionPipeline(_CODEX_EVENT_PARSER, _CODEX_RESPONSE_REDUCER)


class CodexBridge:
    def capabilities(self) -> BridgeCapabilities:
        return BridgeCapabilities(
            agent_type=AgentType.CODEX,
            cli_name="codex",
            supports_tool_events=True,
            supports_usage=True,
            supports_reasoning=True,
            supports_plan_events=True,
            supports_file_change_events=True,
            supports_permission_callbacks=False,
            supports_cancellation=False,
            supports_structured_json_output=True,
            supported_options=[
                "model",
                "sandbox",
                "images",
                "resume_session_id",
                "continue_session",
                "additional_directories",
                "full_auto",
                "dangerously_bypass",
                "skip_git_repo_check",
            ],
        )

    def execute(self, request: AgentRequest) -> AgentResponse:
        request = normalize_request_paths(request)
        command = CommandSpec(
            argv=build_codex_command(request),
            cwd=request.working_directory,
            env=agent_env(AgentType.CODEX, request.provider_options),
            timeout_seconds=request.timeout_seconds,
        )
        output = run_command(command)
        return _CODEX_PIPELINE.parse_output(output)

    def stream(self, request: AgentRequest) -> StreamResult:
        request = normalize_request_paths(request)
        command = CommandSpec(
            argv=build_codex_command(request),
            cwd=request.working_directory,
            env=agent_env(AgentType.CODEX, request.provider_options),
            timeout_seconds=request.timeout_seconds,
        )
        return _CODEX_PIPELINE.stream_command(command)
