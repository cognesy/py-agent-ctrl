from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol

from py_agent_ctrl.api.events import AgentEvent, StreamDiagnostics
from py_agent_ctrl.api.models import AgentResponse, AgentType
from py_agent_ctrl.services.core.subprocess import JsonLine, JsonLinesParser, JsonParseDiagnostics


class ProviderEventParser(Protocol):
    @property
    def agent_type(self) -> AgentType: ...

    def parse_payload(self, payload: dict[str, Any]) -> list[AgentEvent]: ...


class ProviderResponseReducer(Protocol):
    @property
    def agent_type(self) -> AgentType: ...

    def reduce(
        self,
        *,
        events: list[AgentEvent],
        raw_events: list[dict[str, Any]],
        exit_code: int,
        parse_failures: int,
        parse_failure_samples: list[str],
    ) -> AgentResponse: ...


class ResponseReducerFunc(Protocol):
    def __call__(
        self,
        *,
        events: list[AgentEvent],
        raw_events: list[dict[str, Any]],
        exit_code: int,
        parse_failures: int,
        parse_failure_samples: list[str],
    ) -> AgentResponse: ...


EventParserFunc = Callable[[dict[str, Any]], list[AgentEvent]]


@dataclass(frozen=True, slots=True)
class FunctionEventParser:
    agent_type: AgentType
    parser: EventParserFunc

    def parse_payload(self, payload: dict[str, Any]) -> list[AgentEvent]:
        return self.parser(payload)


@dataclass(frozen=True, slots=True)
class FunctionResponseReducer:
    agent_type: AgentType
    reducer: ResponseReducerFunc

    def reduce(
        self,
        *,
        events: list[AgentEvent],
        raw_events: list[dict[str, Any]],
        exit_code: int,
        parse_failures: int,
        parse_failure_samples: list[str],
    ) -> AgentResponse:
        return self.reducer(
            events=events,
            raw_events=raw_events,
            exit_code=exit_code,
            parse_failures=parse_failures,
            parse_failure_samples=parse_failure_samples,
        )


@dataclass(slots=True)
class ProviderParseResult:
    agent_type: AgentType
    events: list[AgentEvent] = field(default_factory=list)
    raw_events: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: JsonParseDiagnostics = field(default_factory=JsonParseDiagnostics)

    @property
    def parse_failures(self) -> int:
        return self.diagnostics.parse_failures

    @property
    def parse_failure_samples(self) -> list[str]:
        return list(self.diagnostics.parse_failure_samples)

    def reduce(self, reducer: ProviderResponseReducer, *, exit_code: int) -> AgentResponse:
        if reducer.agent_type is not self.agent_type:
            msg = f"Reducer for {reducer.agent_type.value} cannot reduce {self.agent_type.value} parse results"
            raise ValueError(msg)
        return reducer.reduce(
            events=self.events,
            raw_events=self.raw_events,
            exit_code=exit_code,
            parse_failures=self.parse_failures,
            parse_failure_samples=self.parse_failure_samples,
        )


def parse_json_lines(text: str, parser: ProviderEventParser) -> ProviderParseResult:
    json_parser = JsonLinesParser()
    result = ProviderParseResult(agent_type=parser.agent_type, diagnostics=json_parser.diagnostics)
    _consume_parsed_lines(json_parser.consume(text), parser, result)
    _consume_parsed_lines(json_parser.finish(), parser, result)
    return result


def parse_json_payloads(payloads: Iterable[dict[str, Any]], parser: ProviderEventParser) -> ProviderParseResult:
    result = ProviderParseResult(agent_type=parser.agent_type)
    for payload in payloads:
        result.raw_events.append(payload)
        result.events.extend(parser.parse_payload(payload))
    return result


def stream_diagnostics_from(
    diagnostics: JsonParseDiagnostics,
    *,
    command_preview: list[str] | None = None,
    cwd: str | None = None,
) -> StreamDiagnostics:
    return StreamDiagnostics(
        parse_failures=diagnostics.parse_failures,
        skipped_non_json_lines=diagnostics.skipped_non_json_lines,
        overlong_lines=diagnostics.overlong_lines,
        parse_failure_samples=list(diagnostics.parse_failure_samples),
        command_preview=list(command_preview or []),
        cwd=cwd,
    )


def _consume_parsed_lines(
    lines: Iterable[JsonLine],
    parser: ProviderEventParser,
    result: ProviderParseResult,
) -> None:
    for line in lines:
        if line.payload is None:
            continue
        payload: dict[str, Any] = dict(line.payload)
        result.raw_events.append(payload)
        result.events.extend(parser.parse_payload(payload))
