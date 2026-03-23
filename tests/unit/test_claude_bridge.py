from py_agent_ctrl.api.models import AgentRequest
from py_agent_ctrl.services.bridges.claude_code.command_builder import build_claude_command
from py_agent_ctrl.services.bridges.claude_code.parser import events_to_response, parse_claude_event
from py_agent_ctrl.api.events import AgentResultEvent, AgentTextEvent, AgentToolCallEvent


def test_build_claude_command_contains_stream_json(monkeypatch):
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.claude_code.command_builder.require_binary",
        lambda *_args, **_kwargs: "/tmp/claude",
    )
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.claude_code.command_builder.shutil.which",
        lambda name: None if name == "stdbuf" else f"/tmp/{name}",
    )

    request = AgentRequest(prompt="hello", max_turns=3, model="claude-sonnet")
    argv = build_claude_command(request)

    assert argv[:3] == ["/tmp/claude", "-p", "hello"]
    assert "--output-format" in argv
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert argv[argv.index("--max-turns") + 1] == "3"


def test_parse_claude_events_to_normalized_response():
    raw_events = [
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "pong"}]},
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "tool-1", "name": "Read", "input": {"path": "README.md"}}],
            },
        },
        {
            "type": "result",
            "subtype": "success",
            "session_id": "sess-1",
            "result": "pong",
            "is_error": False,
            "cost_usd": 0.01,
            "duration_ms": 25,
        },
    ]

    events = [parse_claude_event(raw) for raw in raw_events]
    response = events_to_response(
        events=events,
        raw_events=raw_events,
        exit_code=0,
        parse_failures=0,
        parse_failure_samples=[],
    )

    assert isinstance(events[0], AgentTextEvent)
    assert isinstance(events[1], AgentToolCallEvent)
    assert isinstance(events[2], AgentResultEvent)
    assert response.text == "pong"
    assert response.session_id == "sess-1"
    assert response.tool_calls[0].name == "Read"


def test_events_to_response_extracts_usage_from_result_event():
    raw_events = [
        {
            "type": "result",
            "subtype": "success",
            "session_id": "s1",
            "result": "",
            "is_error": False,
            "cost_usd": 0.005,
            "duration_ms": 500,
            "usage": {
                "input_tokens": 100,
                "output_tokens": 40,
                "cache_creation_input_tokens": 10,
                "cache_read_input_tokens": 5,
            },
        }
    ]
    events = [parse_claude_event(raw) for raw in raw_events]
    response = events_to_response(
        events=events,
        raw_events=raw_events,
        exit_code=0,
        parse_failures=0,
        parse_failure_samples=[],
    )

    assert response.usage is not None
    assert response.usage.input_tokens == 100
    assert response.usage.output_tokens == 40
    assert response.usage.cache_write_tokens == 10
    assert response.usage.cache_read_tokens == 5
    assert response.usage.total_tokens == 155


def test_assistant_event_can_emit_text_and_tool_call():
    raw = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "checking"},
                {"type": "tool_use", "id": "tool-1", "name": "Read", "input": {"path": "README.md"}},
            ],
        },
    }

    from py_agent_ctrl.services.bridges.claude_code.parser import parse_claude_events

    events = parse_claude_events(raw)

    assert [event.type for event in events] == ["text", "tool_call"]
