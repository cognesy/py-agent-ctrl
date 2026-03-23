from __future__ import annotations

from collections.abc import Iterator

from py_agent_ctrl.api.events import AgentEvent, StreamResult
from py_agent_ctrl.api.models import AgentRequest, AgentResponse, AgentType, BridgeCapabilities
from py_agent_ctrl.services.bridges.pi.command_builder import build_pi_command
from py_agent_ctrl.services.bridges.pi.parser import parse_pi_events, pi_response_from_output
from py_agent_ctrl.services.core.env import cleaned_agent_env
from py_agent_ctrl.services.core.subprocess import iter_json_lines, run_process, stream_process


class PiBridge:
    def capabilities(self) -> BridgeCapabilities:
        return BridgeCapabilities(
            agent_type=AgentType.PI,
            cli_name="pi",
            supported_options=["model", "provider", "thinking", "tools", "files", "extensions", "skills", "session_dir"],
        )

    def execute(self, request: AgentRequest) -> AgentResponse:
        output = run_process(
            build_pi_command(request),
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
            events.extend(parse_pi_events(payload))
        return pi_response_from_output(
            events=events,
            raw_events=raw_events,
            exit_code=output.exit_code,
            parse_failures=failures,
            parse_failure_samples=samples,
        )

    def stream(self, request: AgentRequest) -> StreamResult:
        gen, get_exit_code = stream_process(
            build_pi_command(request),
            cwd=request.working_directory,
            env=cleaned_agent_env(),
            timeout_seconds=request.timeout_seconds,
        )

        def _events() -> Iterator[AgentEvent]:
            for payload, _raw_line in gen:
                if payload is None:
                    continue
                yield from parse_pi_events(payload)

        return StreamResult(_events(), get_exit_code)
