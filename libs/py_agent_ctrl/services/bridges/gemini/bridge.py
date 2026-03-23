from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from py_agent_ctrl.api.events import AgentEvent, AgentToolCallEvent, StreamResult
from py_agent_ctrl.api.models import AgentRequest, AgentResponse, AgentType, BridgeCapabilities, ToolCall
from py_agent_ctrl.services.bridges.gemini.command_builder import build_gemini_command
from py_agent_ctrl.services.bridges.gemini.parser import gemini_response_from_output, parse_gemini_events
from py_agent_ctrl.services.core.env import cleaned_agent_env
from py_agent_ctrl.services.core.subprocess import iter_json_lines, run_process, stream_process


class GeminiBridge:
    def capabilities(self) -> BridgeCapabilities:
        return BridgeCapabilities(
            agent_type=AgentType.GEMINI,
            cli_name="gemini",
            supported_options=["model", "approval_mode", "sandbox", "include_directories", "extensions", "allowed_tools", "allowed_mcp_servers", "policy_files", "debug"],
        )

    def execute(self, request: AgentRequest) -> AgentResponse:
        output = run_process(
            build_gemini_command(request),
            cwd=request.working_directory,
            env=cleaned_agent_env(),
            timeout_seconds=request.timeout_seconds,
        )
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
        gen, get_exit_code = stream_process(
            build_gemini_command(request),
            cwd=request.working_directory,
            env=cleaned_agent_env(),
            timeout_seconds=request.timeout_seconds,
        )

        def _events() -> Iterator[AgentEvent]:
            pending_tools: dict[str, dict[str, Any]] = {}
            for payload, _raw_line in gen:
                if payload is None:
                    continue
                event_type = payload.get("type", "")
                if event_type == "tool_use":
                    tool_id = str(payload.get("tool_id", ""))
                    pending_tools[tool_id] = payload
                    continue
                if event_type == "tool_result":
                    tool_id = str(payload.get("tool_id", ""))
                    tool_use = pending_tools.pop(tool_id, {})
                    yield AgentToolCallEvent(
                        tool_call=ToolCall(
                            id=tool_id,
                            name=str(tool_use.get("tool_name", "")),
                            arguments=dict(tool_use.get("parameters", {})),
                            output=payload.get("output") or payload.get("error"),
                            is_error=str(payload.get("status", "")) == "error",
                            raw=payload,
                        ),
                        raw=payload,
                    )
                    continue
                yield from parse_gemini_events(payload)

        return StreamResult(_events(), get_exit_code)
