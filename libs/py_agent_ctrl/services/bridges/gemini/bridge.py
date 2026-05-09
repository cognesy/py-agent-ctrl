from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from py_agent_ctrl.api.events import AgentEvent, AgentToolCallEvent, StreamResult
from py_agent_ctrl.api.models import (
    AgentRequest,
    AgentResponse,
    AgentType,
    BridgeCapabilities,
    ToolCall,
    infer_tool_kind,
    normalize_tool_call_status,
)
from py_agent_ctrl.services.bridges.gemini.command_builder import build_gemini_command
from py_agent_ctrl.services.bridges.gemini.parser import gemini_response_from_output, parse_gemini_events
from py_agent_ctrl.services.core.env import agent_env
from py_agent_ctrl.services.core.parsing import (
    FunctionEventParser,
    FunctionResponseReducer,
)
from py_agent_ctrl.services.core.paths import normalize_request_paths
from py_agent_ctrl.services.core.pipeline import ProviderExecutionPipeline, ProviderExecutionState, StreamPayloadAdapter
from py_agent_ctrl.services.core.subprocess import (
    CommandSpec,
    run_command,
)

_GEMINI_EVENT_PARSER = FunctionEventParser(AgentType.GEMINI, parse_gemini_events)
_GEMINI_RESPONSE_REDUCER = FunctionResponseReducer(AgentType.GEMINI, gemini_response_from_output)
_GEMINI_PIPELINE = ProviderExecutionPipeline(_GEMINI_EVENT_PARSER, _GEMINI_RESPONSE_REDUCER)


def _gemini_stream_payload_adapter() -> StreamPayloadAdapter:
    pending_tools: dict[str, dict[str, Any]] = {}

    def _adapt(
        payload: dict[str, object],
        parsed_events: list[AgentEvent],
        _state: ProviderExecutionState,
    ) -> Iterable[AgentEvent]:
        event_type = str(payload.get("type", ""))
        if event_type == "tool_use":
            tool_id = str(payload.get("tool_id", ""))
            pending_tools[tool_id] = payload
            return []
        if event_type == "tool_result":
            tool_id = str(payload.get("tool_id", ""))
            tool_use = pending_tools.pop(tool_id, {})
            is_error = str(payload.get("status", "")) == "error"
            return [
                AgentToolCallEvent(
                    tool_call=ToolCall(
                        id=tool_id,
                        name=str(tool_use.get("tool_name", "")),
                        kind=infer_tool_kind(str(tool_use.get("tool_name", "")), event_type=event_type),
                        arguments=dict(tool_use.get("parameters", {})),
                        output=payload.get("output") or payload.get("error"),
                        is_error=is_error,
                        status=normalize_tool_call_status(payload.get("status"), is_error=is_error),
                        raw=payload,
                    ),
                    raw=payload,
                )
            ]
        return parsed_events

    return _adapt


class GeminiBridge:
    def capabilities(self) -> BridgeCapabilities:
        return BridgeCapabilities(
            agent_type=AgentType.GEMINI,
            cli_name="gemini",
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
                "approval_mode",
                "sandbox",
                "include_directories",
                "extensions",
                "allowed_tools",
                "allowed_mcp_servers",
                "policy_files",
                "debug",
            ],
        )

    def execute(self, request: AgentRequest) -> AgentResponse:
        request = normalize_request_paths(request)
        command = CommandSpec(
            argv=build_gemini_command(request),
            cwd=request.working_directory,
            env=agent_env(AgentType.GEMINI, request.provider_options),
            timeout_seconds=request.timeout_seconds,
        )
        output = run_command(command)
        return _GEMINI_PIPELINE.parse_output(output)

    def stream(self, request: AgentRequest) -> StreamResult:
        request = normalize_request_paths(request)
        command = CommandSpec(
            argv=build_gemini_command(request),
            cwd=request.working_directory,
            env=agent_env(AgentType.GEMINI, request.provider_options),
            timeout_seconds=request.timeout_seconds,
        )
        pipeline = ProviderExecutionPipeline(
            _GEMINI_EVENT_PARSER,
            _GEMINI_RESPONSE_REDUCER,
            stream_payload_adapter=_gemini_stream_payload_adapter(),
        )
        return pipeline.stream_command(command)
