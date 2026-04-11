from py_agent_ctrl.adapters.acp import event_to_acp_update, session_notification
from py_agent_ctrl.api.events import (
    AgentPlanUpdateEvent,
    AgentReasoningEvent,
    AgentResultEvent,
    AgentTextEvent,
    AgentToolCallEvent,
    AgentUnknownEvent,
    AgentUsageEvent,
)
from py_agent_ctrl.api.models import TokenUsage, ToolCall


def test_acp_adapter_maps_text_event():
    assert event_to_acp_update(AgentTextEvent(text="hello")) == {
        "session_update": "agent_message_chunk",
        "content": {"type": "text", "text": "hello"},
    }


def test_acp_adapter_maps_tool_call_event():
    event = AgentToolCallEvent(
        tool_call=ToolCall(id="tool-1", name="bash", arguments={"command": "pwd"}, output="ok")
    )

    assert event_to_acp_update(event) == {
        "session_update": "tool_call",
        "tool_call_id": "tool-1",
        "title": "bash",
        "status": "completed",
        "raw_input": {"command": "pwd"},
        "raw_output": "ok",
    }


def test_acp_adapter_maps_richer_events():
    assert event_to_acp_update(AgentReasoningEvent(text="thinking")) == {
        "session_update": "agent_thought_chunk",
        "content": {"type": "text", "text": "thinking"},
    }
    assert event_to_acp_update(AgentPlanUpdateEvent(plan=[{"content": "test"}])) == {
        "session_update": "plan",
        "entries": [{"content": "test"}],
    }
    assert event_to_acp_update(AgentUsageEvent(usage=TokenUsage(input_tokens=1, output_tokens=2))) == {
        "session_update": "usage",
        "usage": {"input_tokens": 1, "output_tokens": 2},
    }


def test_acp_adapter_maps_result_and_session_notification():
    event = AgentResultEvent(session_id="provider-session", cost_usd=0.1, duration_ms=5)

    assert event_to_acp_update(event) == {
        "session_update": "session_info",
        "session_id": "provider-session",
        "cost_usd": 0.1,
        "duration_ms": 5,
    }
    assert session_notification("session-1", event) == {
        "session_id": "session-1",
        "update": {
            "session_update": "session_info",
            "session_id": "provider-session",
            "cost_usd": 0.1,
            "duration_ms": 5,
        },
    }


def test_acp_adapter_leaves_unknown_events_unmapped():
    assert event_to_acp_update(AgentUnknownEvent(raw={"type": "new"})) is None
