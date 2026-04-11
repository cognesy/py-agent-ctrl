from __future__ import annotations

from typing import Any

from py_agent_ctrl.api.events import (
    AgentEvent,
    AgentFileChangeEvent,
    AgentPlanUpdateEvent,
    AgentReasoningEvent,
    AgentResultEvent,
    AgentTextEvent,
    AgentToolCallEvent,
    AgentUsageEvent,
    AgentWarningEvent,
)


def event_to_acp_update(event: AgentEvent) -> dict[str, Any] | None:
    if isinstance(event, AgentTextEvent):
        return {
            "session_update": "agent_message_chunk",
            "content": {"type": "text", "text": event.text},
        }
    if isinstance(event, AgentReasoningEvent):
        return {
            "session_update": "agent_thought_chunk",
            "content": {"type": "text", "text": event.text},
        }
    if isinstance(event, AgentToolCallEvent):
        return {
            "session_update": "tool_call",
            "tool_call_id": event.tool_call.id or event.tool_call.name,
            "title": event.tool_call.name,
            "status": event.tool_call.status or ("failed" if event.tool_call.is_error else "completed"),
            "raw_input": event.tool_call.arguments,
            "raw_output": event.tool_call.output,
        }
    if isinstance(event, AgentPlanUpdateEvent):
        return {
            "session_update": "plan",
            "entries": event.plan,
        }
    if isinstance(event, AgentUsageEvent):
        return {
            "session_update": "usage",
            "usage": event.usage.model_dump(exclude_none=True),
        }
    if isinstance(event, AgentWarningEvent):
        return {
            "session_update": "agent_message_chunk",
            "content": {"type": "text", "text": event.message},
            "annotations": [{"audience": ["user"], "kind": "warning"}],
        }
    if isinstance(event, AgentFileChangeEvent):
        return {
            "session_update": "tool_call",
            "tool_call_id": f"file_change:{event.path or ''}",
            "title": "file_change",
            "kind": "edit",
            "status": "completed",
            "locations": [{"path": event.path}] if event.path else None,
            "raw_input": {"path": event.path, "action": event.action},
            "raw_output": event.diff,
        }
    if isinstance(event, AgentResultEvent):
        return {
            "session_update": "session_info",
            "session_id": event.session_id,
            "cost_usd": event.cost_usd,
            "duration_ms": event.duration_ms,
        }
    return None


def session_notification(session_id: str, event: AgentEvent) -> dict[str, Any] | None:
    update = event_to_acp_update(event)
    if update is None:
        return None
    return {"session_id": session_id, "update": update}
