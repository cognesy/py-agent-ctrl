import pytest
from py_agent_ctrl import AgentTextEvent, AgentToolCallEvent, AgentType
from py_agent_ctrl.actions.agents import CodexAction
from py_agent_ctrl.api.events import StreamResult
from py_agent_ctrl.api.models import AgentRequest, AgentResponse, BridgeCapabilities, ToolCall


class FakeBridge:
    def __init__(
        self,
        *,
        execute_error: Exception | None = None,
        stream_events: list[AgentTextEvent | AgentToolCallEvent] | None = None,
    ) -> None:
        self.execute_error = execute_error
        self.stream_events = stream_events

    def capabilities(self) -> BridgeCapabilities:
        return BridgeCapabilities(agent_type=AgentType.CODEX, cli_name="fake")

    def execute(self, request: AgentRequest) -> AgentResponse:
        if self.execute_error:
            raise self.execute_error
        return AgentResponse(
            agent_type=AgentType.CODEX,
            text=f"done:{request.prompt}",
            tool_calls=[ToolCall(id="t1", name="bash", arguments={"command": "pwd"})],
        )

    def stream(self, request: AgentRequest) -> StreamResult:
        events = iter(
            self.stream_events
            or [
                AgentTextEvent(text=f"stream:{request.prompt}"),
                AgentToolCallEvent(tool_call=ToolCall(id="t2", name="read", arguments={"path": "README.md"})),
            ]
        )
        return StreamResult(events, lambda: 7)


def test_execute_callbacks_fire_from_normalized_response():
    text_chunks: list[str] = []
    tool_names: list[str] = []
    completions: list[AgentResponse] = []
    action = (
        CodexAction(FakeBridge())
        .on_text(text_chunks.append)
        .on_tool_call(lambda tool_call: tool_names.append(tool_call.name))
        .on_complete(completions.append)
    )

    response = action.execute("go")

    assert response.text == "done:go"
    assert text_chunks == ["done:go"]
    assert tool_names == ["bash"]
    assert completions == [response]


def test_stream_callbacks_wiretap_events_without_consuming_exit_code():
    event_types: list[str] = []
    text_chunks: list[str] = []
    tool_names: list[str] = []
    action = (
        CodexAction(FakeBridge())
        .on_event(lambda event: event_types.append(event.type))
        .on_text(text_chunks.append)
        .on_tool_call(lambda tool_call: tool_names.append(tool_call.name))
    )

    result = action.stream("go")
    events = list(result)

    assert [event.type for event in events] == ["text", "tool_call"]
    assert event_types == ["text", "tool_call"]
    assert text_chunks == ["stream:go"]
    assert tool_names == ["read"]
    assert result.exit_code == 7


def test_execute_error_callback_fires_before_reraising():
    errors: list[Exception] = []
    expected = RuntimeError("boom")
    action = CodexAction(FakeBridge(execute_error=expected)).on_error(errors.append)

    with pytest.raises(RuntimeError, match="boom"):
        action.execute("go")

    assert errors == [expected]


def test_stream_text_callbacks_dedupe_cumulative_chunks_without_changing_iteration():
    text_chunks: list[str] = []
    bridge = FakeBridge(
        stream_events=[
            AgentTextEvent(text="hel"),
            AgentTextEvent(text="hello"),
            AgentTextEvent(text="hello world"),
        ]
    )
    action = CodexAction(bridge).on_text(text_chunks.append)

    events = list(action.stream("go"))

    assert [event.text for event in events if isinstance(event, AgentTextEvent)] == ["hel", "hello", "hello world"]
    assert text_chunks == ["hel", "lo", " world"]


def test_stream_text_callbacks_suppress_internal_json_but_event_wiretap_still_sees_it():
    text_chunks: list[str] = []
    event_texts: list[str] = []
    internal = '{"type":"output","data":{"parentUuid":null,"sessionId":"s1","userType":"external"}}'
    bridge = FakeBridge(
        stream_events=[
            AgentTextEvent(text="hello"),
            AgentTextEvent(text=internal),
            AgentTextEvent(text="hello world"),
        ]
    )
    action = (
        CodexAction(bridge)
        .on_text(text_chunks.append)
        .on_event(lambda event: event_texts.append(event.text) if isinstance(event, AgentTextEvent) else None)
    )

    events = list(action.stream("go"))

    assert [event.text for event in events if isinstance(event, AgentTextEvent)] == ["hello", internal, "hello world"]
    assert event_texts == ["hello", internal, "hello world"]
    assert text_chunks == ["hello", " world"]
