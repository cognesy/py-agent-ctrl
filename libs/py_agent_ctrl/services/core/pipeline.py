from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

from py_agent_ctrl.api.events import AgentEvent, StreamResult
from py_agent_ctrl.api.models import AgentResponse
from py_agent_ctrl.services.core.parsing import (
    ProviderEventParser,
    ProviderParseResult,
    ProviderResponseReducer,
    parse_json_lines,
    stream_diagnostics_from,
)
from py_agent_ctrl.services.core.subprocess import (
    CommandSpec,
    JsonLine,
    JsonParseDiagnostics,
    ProcessOutput,
    stream_command_json_lines,
)


@dataclass(slots=True)
class ProviderExecutionState:
    event_parser: ProviderEventParser
    result: ProviderParseResult

    @classmethod
    def create(
        cls,
        event_parser: ProviderEventParser,
        *,
        diagnostics: JsonParseDiagnostics | None = None,
    ) -> ProviderExecutionState:
        return cls(
            event_parser=event_parser,
            result=ProviderParseResult(
                agent_type=event_parser.agent_type,
                diagnostics=diagnostics or JsonParseDiagnostics(),
            ),
        )

    @property
    def events(self) -> list[AgentEvent]:
        return self.result.events

    @property
    def raw_events(self) -> list[dict[str, object]]:
        return self.result.raw_events

    @property
    def diagnostics(self) -> JsonParseDiagnostics:
        return self.result.diagnostics

    def record_payload(self, payload: dict[str, object]) -> list[AgentEvent]:
        raw_payload = dict(payload)
        events = self.event_parser.parse_payload(raw_payload)
        self.result.raw_events.append(raw_payload)
        self.result.events.extend(events)
        return events

    def record_json_line(self, line: JsonLine) -> list[AgentEvent]:
        if line.payload is None:
            return []
        return self.record_payload(line.payload)

    def reduce(self, reducer: ProviderResponseReducer, *, exit_code: int) -> AgentResponse:
        return self.result.reduce(reducer, exit_code=exit_code)


StreamPayloadAdapter = Callable[
    [dict[str, object], list[AgentEvent], ProviderExecutionState],
    Iterable[AgentEvent],
]


@dataclass(frozen=True, slots=True)
class ProviderExecutionPipeline:
    event_parser: ProviderEventParser
    response_reducer: ProviderResponseReducer
    stream_payload_adapter: StreamPayloadAdapter | None = None

    def new_state(self, *, diagnostics: JsonParseDiagnostics | None = None) -> ProviderExecutionState:
        return ProviderExecutionState.create(self.event_parser, diagnostics=diagnostics)

    def parse_output(self, output: ProcessOutput) -> AgentResponse:
        parse_result = parse_json_lines(output.stdout, self.event_parser)
        return parse_result.reduce(self.response_reducer, exit_code=output.exit_code)

    def stream_command(self, command: CommandSpec) -> StreamResult:
        diagnostics = JsonParseDiagnostics()
        state = self.new_state(diagnostics=diagnostics)
        gen, get_exit_code = stream_command_json_lines(command, diagnostics=diagnostics)

        def _events() -> Iterator[AgentEvent]:
            for payload, _raw_line in gen:
                if payload is None:
                    continue
                parsed_events = state.record_payload(payload)
                if self.stream_payload_adapter is None:
                    yield from parsed_events
                    continue
                yield from self.stream_payload_adapter(payload, parsed_events, state)

        return StreamResult(
            _events(),
            get_exit_code,
            lambda: stream_diagnostics_from(diagnostics, command_preview=command.argv[:5], cwd=command.cwd),
        )

    def reduce_state(self, state: ProviderExecutionState, *, exit_code: int) -> AgentResponse:
        if state.event_parser.agent_type is not self.event_parser.agent_type:
            msg = (
                f"Pipeline for {self.event_parser.agent_type.value} cannot reduce "
                f"{state.event_parser.agent_type.value} execution state"
            )
            raise ValueError(msg)
        return state.reduce(self.response_reducer, exit_code=exit_code)
