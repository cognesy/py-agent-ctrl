from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from py_agent_ctrl.api.events import AgentEvent, AgentToolCallEvent, StreamDiagnostics, StreamResult
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
from py_agent_ctrl.services.core.paths import normalize_request_paths
from py_agent_ctrl.services.core.subprocess import (
    CommandSpec,
    JsonParseDiagnostics,
    iter_json_lines,
    run_command,
    stream_command_json_lines,
)


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
        events: list[AgentEvent] = []
        raw_events: list[dict[str, object]] = []
        failures = 0
        samples: list[str] = []
        for payload, raw_line in iter_json_lines(output.stdout):
            if payload is None:
                failures += 1
                if len(samples) < 5:
                    samples.append(raw_line)
                continue
            raw_events.append(payload)
            events.extend(parse_gemini_events(payload))
        return gemini_response_from_output(
            events=events,
            raw_events=raw_events,
            exit_code=output.exit_code,
            parse_failures=failures,
            parse_failure_samples=samples,
        )

    def stream(self, request: AgentRequest) -> StreamResult:
        request = normalize_request_paths(request)
        command = CommandSpec(
            argv=build_gemini_command(request),
            cwd=request.working_directory,
            env=agent_env(AgentType.GEMINI, request.provider_options),
            timeout_seconds=request.timeout_seconds,
        )
        json_diagnostics = JsonParseDiagnostics()
        gen, get_exit_code = stream_command_json_lines(command, diagnostics=json_diagnostics)

        def _events() -> Iterator[AgentEvent]:
            pending_tools: dict[str, dict[str, Any]] = {}
            for payload, _raw_line in gen:
                if payload is None:
                    continue
                event_type = str(payload.get("type", ""))
                if event_type == "tool_use":
                    tool_id = str(payload.get("tool_id", ""))
                    pending_tools[tool_id] = payload
                    continue
                if event_type == "tool_result":
                    tool_id = str(payload.get("tool_id", ""))
                    tool_use = pending_tools.pop(tool_id, {})
                    is_error = str(payload.get("status", "")) == "error"
                    yield AgentToolCallEvent(
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
                    continue
                yield from parse_gemini_events(payload)

        return StreamResult(
            _events(),
            get_exit_code,
            lambda: StreamDiagnostics(
                parse_failures=json_diagnostics.parse_failures,
                skipped_non_json_lines=json_diagnostics.skipped_non_json_lines,
                overlong_lines=json_diagnostics.overlong_lines,
                parse_failure_samples=list(json_diagnostics.parse_failure_samples),
                command_preview=command.argv[:5],
                cwd=command.cwd,
            ),
        )
