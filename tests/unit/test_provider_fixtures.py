from pathlib import Path

import pytest
from py_agent_ctrl.api.events import AgentTextEvent, AgentToolCallEvent, AgentUnknownEvent
from py_agent_ctrl.api.models import AgentType, ToolCallPhase, ToolCallStatus, ToolKind
from py_agent_ctrl.services.bridges.claude_code.parser import events_to_response, parse_claude_events
from py_agent_ctrl.services.bridges.codex.parser import codex_response_from_output, parse_codex_events
from py_agent_ctrl.services.bridges.gemini.bridge import _gemini_stream_payload_adapter
from py_agent_ctrl.services.bridges.gemini.parser import gemini_response_from_output, parse_gemini_events
from py_agent_ctrl.services.bridges.opencode.parser import opencode_response_from_output, parse_opencode_events
from py_agent_ctrl.services.bridges.pi.parser import parse_pi_events, pi_response_from_output
from py_agent_ctrl.services.core.parsing import FunctionEventParser, FunctionResponseReducer, parse_json_lines
from py_agent_ctrl.services.core.pipeline import ProviderExecutionPipeline
from py_agent_ctrl.services.core.subprocess import JsonLinesParser

FIXTURES = Path(__file__).parents[1] / "fixtures"

PROVIDER_FIXTURE_CASES = [
    (
        "claude_code/basic_stream.jsonl",
        AgentType.CLAUDE_CODE,
        parse_claude_events,
        events_to_response,
    ),
    (
        "codex/basic_stream.jsonl",
        AgentType.CODEX,
        parse_codex_events,
        codex_response_from_output,
    ),
    (
        "codex/malformed_and_unknown.jsonl",
        AgentType.CODEX,
        parse_codex_events,
        codex_response_from_output,
    ),
    (
        "gemini/basic_stream.jsonl",
        AgentType.GEMINI,
        parse_gemini_events,
        gemini_response_from_output,
    ),
    (
        "opencode/basic_stream.jsonl",
        AgentType.OPENCODE,
        parse_opencode_events,
        opencode_response_from_output,
    ),
    (
        "pi/basic_stream.jsonl",
        AgentType.PI,
        parse_pi_events,
        pi_response_from_output,
    ),
]


def _response_without_execution_id(response):
    data = response.model_dump()
    data.pop("execution_id", None)
    return data


def test_claude_code_basic_stream_fixture_matches_normalized_golden_output():
    parse_result = parse_json_lines(
        (FIXTURES / "claude_code" / "basic_stream.jsonl").read_text(),
        FunctionEventParser(AgentType.CLAUDE_CODE, parse_claude_events),
    )
    response = parse_result.reduce(
        FunctionResponseReducer(AgentType.CLAUDE_CODE, events_to_response),
        exit_code=0,
    )

    assert parse_result.diagnostics.parse_failures == 0
    assert [event.type for event in parse_result.events] == ["text", "tool_call", "result"]
    assert isinstance(parse_result.events[0], AgentTextEvent)
    assert isinstance(parse_result.events[1], AgentToolCallEvent)
    assert response.text == "pong"
    assert response.session_id == "sess-1"
    assert response.cost_usd == 0.01
    assert response.duration_ms == 25
    assert response.usage is not None
    assert response.usage.total_tokens == 155
    assert response.tool_calls[0].name == "Read"
    assert response.tool_calls[0].kind is ToolKind.READ
    assert response.tool_calls[0].status is ToolCallStatus.PENDING
    assert response.tool_calls[0].phase is ToolCallPhase.STARTED


def test_codex_basic_stream_fixture_matches_normalized_golden_output():
    parse_result = parse_json_lines(
        (FIXTURES / "codex" / "basic_stream.jsonl").read_text(),
        FunctionEventParser(AgentType.CODEX, parse_codex_events),
    )
    response = parse_result.reduce(
        FunctionResponseReducer(AgentType.CODEX, codex_response_from_output),
        exit_code=0,
    )

    assert parse_result.diagnostics.parse_failures == 0
    assert [event.type for event in parse_result.events] == [
        "result",
        "text",
        "tool_call",
        "tool_call",
        "result",
        "usage",
        "unknown",
    ]
    assert response.session_id == "thread_stream"
    assert response.text == "Hello from codex"
    assert response.usage is not None
    assert response.usage.input_tokens == 9
    assert response.tool_calls[0].name == "bash"
    assert response.tool_calls[0].kind is ToolKind.EXECUTE
    assert response.tool_calls[0].status is ToolCallStatus.FAILED
    assert response.tool_calls[0].phase is ToolCallPhase.FAILED
    assert response.tool_calls[0].raw["item"]["status"] == "completed"
    assert response.tool_calls[1].name == "web_search"
    assert response.tool_calls[1].kind is ToolKind.SEARCH
    assert response.tool_calls[1].phase is ToolCallPhase.COMPLETED


def test_malformed_and_unknown_fixture_records_parse_failures_without_crashing():
    parse_result = parse_json_lines(
        (FIXTURES / "codex" / "malformed_and_unknown.jsonl").read_text(),
        FunctionEventParser(AgentType.CODEX, parse_codex_events),
    )

    assert parse_result.diagnostics.parse_failures == 2
    assert parse_result.diagnostics.skipped_non_json_lines == 1
    assert len(parse_result.diagnostics.parse_failure_samples) == 2
    assert [event.type for event in parse_result.events] == ["result", "unknown"]
    assert isinstance(parse_result.events[-1], AgentUnknownEvent)
    assert parse_result.events[-1].raw == {"type": "provider.new_event", "payload": {"kept": True}}


def test_gemini_basic_stream_fixture_matches_normalized_golden_output():
    parse_result = parse_json_lines(
        (FIXTURES / "gemini" / "basic_stream.jsonl").read_text(),
        FunctionEventParser(AgentType.GEMINI, parse_gemini_events),
    )
    response = parse_result.reduce(
        FunctionResponseReducer(AgentType.GEMINI, gemini_response_from_output),
        exit_code=0,
    )

    assert parse_result.diagnostics.parse_failures == 0
    assert [event.type for event in parse_result.events] == ["result", "text", "unknown", "unknown", "result"]
    assert response.session_id == "gemini-session"
    assert response.text == "Hello"
    assert response.usage is not None
    assert response.usage.cache_read_tokens == 5
    assert response.tool_calls[0].name == "read_file"
    assert response.tool_calls[0].kind is ToolKind.READ
    assert response.tool_calls[0].status is ToolCallStatus.COMPLETED
    assert response.tool_calls[0].phase is ToolCallPhase.COMPLETED


def test_gemini_stream_adapter_preserves_tool_pairing_for_live_events():
    parse_result = parse_json_lines(
        (FIXTURES / "gemini" / "basic_stream.jsonl").read_text(),
        FunctionEventParser(AgentType.GEMINI, parse_gemini_events),
    )
    pipeline = ProviderExecutionPipeline(
        FunctionEventParser(AgentType.GEMINI, parse_gemini_events),
        FunctionResponseReducer(AgentType.GEMINI, gemini_response_from_output),
    )
    state = pipeline.new_state()
    adapter = _gemini_stream_payload_adapter()
    streamed_events = []

    for payload in parse_result.raw_events:
        parsed_events = state.record_payload(payload)
        streamed_events.extend(adapter(payload, parsed_events, state))

    assert [event.type for event in state.events] == ["result", "text", "unknown", "unknown", "result"]
    assert [event.type for event in streamed_events] == ["result", "text", "tool_call", "result"]
    assert isinstance(streamed_events[2], AgentToolCallEvent)
    assert streamed_events[2].tool_call.name == "read_file"
    assert streamed_events[2].tool_call.kind is ToolKind.READ
    assert streamed_events[2].tool_call.status is ToolCallStatus.COMPLETED
    assert streamed_events[2].phase is ToolCallPhase.COMPLETED
    assert streamed_events[2].tool_call.phase is ToolCallPhase.COMPLETED


def test_opencode_basic_stream_fixture_matches_normalized_golden_output():
    parse_result = parse_json_lines(
        (FIXTURES / "opencode" / "basic_stream.jsonl").read_text(),
        FunctionEventParser(AgentType.OPENCODE, parse_opencode_events),
    )
    response = parse_result.reduce(
        FunctionResponseReducer(AgentType.OPENCODE, opencode_response_from_output),
        exit_code=0,
    )

    assert parse_result.diagnostics.parse_failures == 0
    assert [event.type for event in parse_result.events] == ["unknown", "text", "tool_call", "result"]
    assert response.session_id == "sess_stream"
    assert response.text == "Hello OpenCode"
    assert response.cost_usd == 0.42
    assert response.usage is not None
    assert response.usage.reasoning_tokens == 1
    assert response.tool_calls[0].name == "bash"
    assert response.tool_calls[0].kind is ToolKind.EXECUTE
    assert response.tool_calls[0].status is ToolCallStatus.COMPLETED
    assert response.tool_calls[0].phase is ToolCallPhase.COMPLETED


def test_pi_basic_stream_fixture_matches_normalized_golden_output():
    parse_result = parse_json_lines(
        (FIXTURES / "pi" / "basic_stream.jsonl").read_text(),
        FunctionEventParser(AgentType.PI, parse_pi_events),
    )
    response = parse_result.reduce(
        FunctionResponseReducer(AgentType.PI, pi_response_from_output),
        exit_code=0,
    )

    assert parse_result.diagnostics.parse_failures == 0
    assert [event.type for event in parse_result.events] == ["result", "text", "tool_call", "result"]
    assert response.session_id == "pi-session"
    assert response.text == "Hello world"
    assert response.cost_usd == 0.12
    assert response.usage is not None
    assert response.usage.total_tokens == 10
    assert response.tool_calls[0].name == "bash"
    assert response.tool_calls[0].kind is ToolKind.EXECUTE
    assert response.tool_calls[0].status is ToolCallStatus.COMPLETED
    assert response.tool_calls[0].phase is ToolCallPhase.COMPLETED


def test_parse_result_rejects_wrong_provider_reducer():
    parse_result = parse_json_lines(
        (FIXTURES / "codex" / "basic_stream.jsonl").read_text(),
        FunctionEventParser(AgentType.CODEX, parse_codex_events),
    )

    with pytest.raises(ValueError, match="cannot reduce"):
        parse_result.reduce(FunctionResponseReducer(AgentType.CLAUDE_CODE, events_to_response), exit_code=0)


@pytest.mark.parametrize(("fixture_path", "agent_type", "parse_events", "reduce_response"), PROVIDER_FIXTURE_CASES)
def test_stream_pipeline_state_matches_aggregate_fixture_response(
    fixture_path,
    agent_type,
    parse_events,
    reduce_response,
):
    text = (FIXTURES / fixture_path).read_text()
    event_parser = FunctionEventParser(agent_type, parse_events)
    response_reducer = FunctionResponseReducer(agent_type, reduce_response)
    aggregate_result = parse_json_lines(text, event_parser)
    aggregate_response = aggregate_result.reduce(response_reducer, exit_code=0)

    pipeline = ProviderExecutionPipeline(event_parser, response_reducer)
    json_parser = JsonLinesParser()
    state = pipeline.new_state(diagnostics=json_parser.diagnostics)
    for raw_line in text.splitlines():
        parsed = json_parser.parse_line(raw_line)
        if parsed is not None:
            state.record_json_line(parsed)

    stream_response = pipeline.reduce_state(state, exit_code=0)

    assert [event.type for event in state.events] == [event.type for event in aggregate_result.events]
    assert state.raw_events == aggregate_result.raw_events
    assert state.diagnostics.parse_failures == aggregate_result.diagnostics.parse_failures
    assert state.diagnostics.skipped_non_json_lines == aggregate_result.diagnostics.skipped_non_json_lines
    assert state.diagnostics.parse_failure_samples == aggregate_result.diagnostics.parse_failure_samples
    assert _response_without_execution_id(stream_response) == _response_without_execution_id(aggregate_response)
