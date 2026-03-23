from __future__ import annotations

from collections.abc import Iterator

from py_agent_ctrl.api.events import AgentEvent, StreamResult
from py_agent_ctrl.api.models import AgentRequest, AgentResponse, AgentType, BridgeCapabilities
from py_agent_ctrl.services.bridges.opencode.command_builder import build_opencode_command
from py_agent_ctrl.services.bridges.opencode.parser import opencode_response_from_output, parse_opencode_events
from py_agent_ctrl.services.core.env import cleaned_agent_env
from py_agent_ctrl.services.core.subprocess import iter_json_lines, run_process, stream_process


class OpenCodeBridge:
    def capabilities(self) -> BridgeCapabilities:
        return BridgeCapabilities(
            agent_type=AgentType.OPENCODE,
            cli_name="opencode",
            supported_options=["model", "agent", "files", "title", "share_session", "resume_session_id", "continue_session"],
        )

    def execute(self, request: AgentRequest) -> AgentResponse:
        output = run_process(
            build_opencode_command(request),
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
            events.extend(parse_opencode_events(payload))
        return opencode_response_from_output(
            events=events,
            raw_events=raw_events,
            exit_code=output.exit_code,
            parse_failures=failures,
            parse_failure_samples=samples,
        )

    def stream(self, request: AgentRequest) -> StreamResult:
        gen, get_exit_code = stream_process(
            build_opencode_command(request),
            cwd=request.working_directory,
            env=cleaned_agent_env(),
            timeout_seconds=request.timeout_seconds,
        )

        def _events() -> Iterator[AgentEvent]:
            for payload, _raw_line in gen:
                if payload is None:
                    continue
                yield from parse_opencode_events(payload)

        return StreamResult(_events(), get_exit_code)
