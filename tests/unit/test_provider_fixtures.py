from pathlib import Path

from py_agent_ctrl.api.events import AgentTextEvent, AgentToolCallEvent, AgentUnknownEvent
from py_agent_ctrl.api.models import ToolCallStatus, ToolKind
from py_agent_ctrl.services.bridges.claude_code.parser import events_to_response, parse_claude_events
from py_agent_ctrl.services.bridges.codex.parser import codex_response_from_output, parse_codex_events
from py_agent_ctrl.services.core.subprocess import JsonLinesParser

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _payloads(path: Path) -> tuple[list[dict[str, object]], JsonLinesParser]:
    parser = JsonLinesParser()
    payloads: list[dict[str, object]] = []
    for line in parser.consume(path.read_text()):
        if line.payload is not None:
            payloads.append(line.payload)
    for line in parser.finish():
        if line.payload is not None:
            payloads.append(line.payload)
    return payloads, parser


def test_claude_code_basic_stream_fixture_matches_normalized_golden_output():
    raw_events, parser = _payloads(FIXTURES / "claude_code" / "basic_stream.jsonl")
    events = [event for raw in raw_events for event in parse_claude_events(raw)]
    response = events_to_response(
        events=events,
        raw_events=raw_events,
        exit_code=0,
        parse_failures=parser.diagnostics.parse_failures,
        parse_failure_samples=parser.diagnostics.parse_failure_samples,
    )

    assert parser.diagnostics.parse_failures == 0
    assert [event.type for event in events] == ["text", "tool_call", "result"]
    assert isinstance(events[0], AgentTextEvent)
    assert isinstance(events[1], AgentToolCallEvent)
    assert response.text == "pong"
    assert response.session_id == "sess-1"
    assert response.cost_usd == 0.01
    assert response.duration_ms == 25
    assert response.usage is not None
    assert response.usage.total_tokens == 155
    assert response.tool_calls[0].name == "Read"
    assert response.tool_calls[0].kind is ToolKind.READ
    assert response.tool_calls[0].status is ToolCallStatus.PENDING


def test_codex_basic_stream_fixture_matches_normalized_golden_output():
    raw_events, parser = _payloads(FIXTURES / "codex" / "basic_stream.jsonl")
    events = [event for raw in raw_events for event in parse_codex_events(raw)]
    response = codex_response_from_output(
        events=events,
        raw_events=raw_events,
        exit_code=0,
        parse_failures=parser.diagnostics.parse_failures,
        parse_failure_samples=parser.diagnostics.parse_failure_samples,
    )

    assert parser.diagnostics.parse_failures == 0
    assert [event.type for event in events] == ["result", "text", "tool_call", "tool_call", "result", "usage", "unknown"]
    assert response.session_id == "thread_stream"
    assert response.text == "Hello from codex"
    assert response.usage is not None
    assert response.usage.input_tokens == 9
    assert response.tool_calls[0].name == "bash"
    assert response.tool_calls[0].kind is ToolKind.EXECUTE
    assert response.tool_calls[0].status is ToolCallStatus.FAILED
    assert response.tool_calls[0].raw["item"]["status"] == "completed"
    assert response.tool_calls[1].name == "web_search"
    assert response.tool_calls[1].kind is ToolKind.SEARCH


def test_malformed_and_unknown_fixture_records_parse_failures_without_crashing():
    raw_events, parser = _payloads(FIXTURES / "codex" / "malformed_and_unknown.jsonl")
    events = [event for raw in raw_events for event in parse_codex_events(raw)]

    assert parser.diagnostics.parse_failures == 2
    assert parser.diagnostics.skipped_non_json_lines == 1
    assert len(parser.diagnostics.parse_failure_samples) == 2
    assert [event.type for event in events] == ["result", "unknown"]
    assert isinstance(events[-1], AgentUnknownEvent)
    assert events[-1].raw == {"type": "provider.new_event", "payload": {"kept": True}}
