from __future__ import annotations

from collections.abc import Iterator

from py_agent_ctrl.api.events import AgentEvent, StreamResult
from py_agent_ctrl.api.models import AgentRequest, AgentResponse, AgentType, BridgeCapabilities
from py_agent_ctrl.services.bridges.claude_code.command_builder import build_claude_command
from py_agent_ctrl.services.bridges.claude_code.parser import events_to_response, parse_claude_events
from py_agent_ctrl.services.core.env import cleaned_agent_env
from py_agent_ctrl.services.core.subprocess import iter_json_lines, run_process, stream_process


class ClaudeCodeBridge:
    def capabilities(self) -> BridgeCapabilities:
        return BridgeCapabilities(
            agent_type=AgentType.CLAUDE_CODE,
            cli_name="claude",
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
        argv = build_claude_command(request)
        output = run_process(
            argv,
            cwd=request.working_directory,
            env=cleaned_agent_env(),
            timeout_seconds=request.timeout_seconds,
        )
        events: list[AgentEvent] = []
        raw_events: list[dict[str, object]] = []
        parse_failures = 0
        parse_failure_samples: list[str] = []
        for payload, raw_line in iter_json_lines(output.stdout):
            if payload is None:
                parse_failures += 1
                if len(parse_failure_samples) < 5:
                    parse_failure_samples.append(raw_line)
                continue
            raw_events.append(payload)
            events.extend(parse_claude_events(payload))

        return events_to_response(
            events=events,
            raw_events=raw_events,
            exit_code=output.exit_code,
            parse_failures=parse_failures,
            parse_failure_samples=parse_failure_samples,
        )

    def stream(self, request: AgentRequest) -> StreamResult:
        gen, get_exit_code = stream_process(
            build_claude_command(request),
            cwd=request.working_directory,
            env=cleaned_agent_env(),
            timeout_seconds=request.timeout_seconds,
        )

        def _events() -> Iterator[AgentEvent]:
            for payload, _raw_line in gen:
                if payload is None:
                    continue
                yield from parse_claude_events(payload)

        return StreamResult(_events(), get_exit_code)
