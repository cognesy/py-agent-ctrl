from __future__ import annotations

import json
from typing import Any

from py_agent_ctrl.api.events import (
    AgentEvent,
    AgentPlanUpdateEvent,
    AgentReasoningEvent,
    AgentResultEvent,
    AgentTextEvent,
    AgentToolCallEvent,
    AgentUnknownEvent,
    AgentUsageEvent,
)
from py_agent_ctrl.api.models import (
    AgentResponse,
    AgentType,
    TokenUsage,
    ToolCall,
    infer_tool_call_phase,
    infer_tool_kind,
    normalize_tool_call_status,
)


def parse_codex_events(raw: dict[str, Any]) -> list[AgentEvent]:
    event_type = raw.get("type", "")
    if not event_type:
        return [AgentTextEvent(text=json.dumps(raw), raw=raw)]
    if event_type == "thread.started":
        return [AgentResultEvent(session_id=raw.get("thread_id"), raw=raw)]
    if event_type == "item.completed":
        item = raw.get("item", {})
        item_type = item.get("type")
        item_id = item.get("id")
        if item_type == "agent_message":
            return [AgentTextEvent(text=str(item.get("text", "")), raw=raw)]
        if item_type == "command_execution":
            is_error = int(item.get("exit_code", 0) or 0) != 0
            status = normalize_tool_call_status(item.get("status"), is_error=is_error)
            phase = infer_tool_call_phase(status)
            return [
                AgentToolCallEvent(
                    tool_call=ToolCall(
                        id=item_id,
                        name="bash",
                        kind=infer_tool_kind("bash", event_type=item_type),
                        arguments={"command": item.get("command", "")},
                        output=item.get("output"),
                        is_error=is_error,
                        status=status,
                        phase=phase,
                        raw=raw,
                    ),
                    phase=phase,
                    raw=raw,
                )
            ]
        if item_type == "mcp_tool_call":
            is_error = str(item.get("status", "")) in {"error", "failed"}
            status = normalize_tool_call_status(item.get("status"), is_error=is_error)
            phase = infer_tool_call_phase(status)
            return [
                AgentToolCallEvent(
                    tool_call=ToolCall(
                        id=item_id,
                        name=str(item.get("tool", "")),
                        kind=infer_tool_kind(str(item.get("tool", "")), event_type=item_type),
                        arguments=dict(item.get("arguments", {})),
                        output=item.get("result"),
                        is_error=is_error,
                        status=status,
                        phase=phase,
                        raw=raw,
                    ),
                    phase=phase,
                    raw=raw,
                )
            ]
        if item_type == "file_change":
            status = normalize_tool_call_status(item.get("status"))
            phase = infer_tool_call_phase(status)
            return [
                AgentToolCallEvent(
                    tool_call=ToolCall(
                        id=item_id,
                        name="file_change",
                        kind=infer_tool_kind("file_change", event_type=item_type),
                        arguments={"path": item.get("path", ""), "action": item.get("action", "")},
                        output=item.get("diff"),
                        status=status,
                        phase=phase,
                        raw=raw,
                    ),
                    phase=phase,
                    raw=raw,
                )
            ]
        if item_type == "web_search":
            status = normalize_tool_call_status(item.get("status"))
            phase = infer_tool_call_phase(status)
            return [
                AgentToolCallEvent(
                    tool_call=ToolCall(
                        id=item_id,
                        name="web_search",
                        kind=infer_tool_kind("web_search", event_type=item_type),
                        arguments={"query": item.get("query", "")},
                        output=item.get("results"),
                        status=status,
                        phase=phase,
                        raw=raw,
                    ),
                    phase=phase,
                    raw=raw,
                )
            ]
        if item_type == "plan_update":
            status = normalize_tool_call_status(item.get("status"))
            phase = infer_tool_call_phase(status)
            return [
                AgentPlanUpdateEvent(plan=item.get("plan"), raw=raw),
                AgentToolCallEvent(
                    tool_call=ToolCall(
                        id=item_id,
                        name="plan_update",
                        kind=infer_tool_kind("plan_update", event_type=item_type),
                        arguments={},
                        output=item.get("plan"),
                        status=status,
                        phase=phase,
                        raw=raw,
                    ),
                    phase=phase,
                    raw=raw,
                ),
            ]
        if item_type == "reasoning":
            text = str(item.get("text", "") or "")
            status = normalize_tool_call_status(item.get("status"))
            phase = infer_tool_call_phase(status)
            return [
                AgentReasoningEvent(text=text, raw=raw),
                AgentToolCallEvent(
                    tool_call=ToolCall(
                        id=item_id,
                        name="reasoning",
                        kind=infer_tool_kind("reasoning", event_type=item_type),
                        arguments={},
                        output=item.get("text"),
                        status=status,
                        phase=phase,
                        raw=raw,
                    ),
                    phase=phase,
                    raw=raw,
                ),
            ]
        status = normalize_tool_call_status(item.get("status"))
        phase = infer_tool_call_phase(status)
        return [
            AgentToolCallEvent(
                tool_call=ToolCall(
                    id=item_id,
                    name=str(item_type or "unknown"),
                    kind=infer_tool_kind(str(item_type or "unknown"), event_type=item_type),
                    arguments={},
                    output=item,
                    status=status,
                    phase=phase,
                    raw=raw,
                ),
                phase=phase,
                raw=raw,
            )
        ]
    if event_type == "turn.completed":
        usage = raw.get("usage", {})
        events: list[AgentEvent] = [AgentResultEvent(raw=raw)]
        if isinstance(usage, dict):
            events.append(
                AgentUsageEvent(
                    usage=TokenUsage(
                        input_tokens=usage.get("input_tokens"),
                        output_tokens=usage.get("output_tokens"),
                        total_tokens=(usage.get("input_tokens", 0) or 0) + (usage.get("output_tokens", 0) or 0),
                        cache_read_tokens=usage.get("cached_input_tokens"),
                    ),
                    raw=raw,
                )
            )
        events.append(AgentUnknownEvent(raw={"usage": usage}))
        return events
    return [AgentUnknownEvent(raw=raw)]


def codex_response_from_output(
    *,
    events: list[AgentEvent],
    raw_events: list[dict[str, Any]],
    exit_code: int,
    parse_failures: int,
    parse_failure_samples: list[str],
) -> AgentResponse:
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    session_id: str | None = None
    usage: TokenUsage | None = None

    for event in events:
        if isinstance(event, AgentTextEvent):
            text_parts.append(event.text)
        elif isinstance(event, AgentToolCallEvent):
            tool_calls.append(event.tool_call)
        elif isinstance(event, AgentResultEvent):
            session_id = event.session_id or session_id
        elif isinstance(event, AgentUsageEvent):
            usage = event.usage
        elif isinstance(event, AgentUnknownEvent):
            usage_data = event.raw.get("usage")
            if isinstance(usage_data, dict):
                usage = TokenUsage(
                    input_tokens=usage_data.get("input_tokens"),
                    output_tokens=usage_data.get("output_tokens"),
                    total_tokens=(usage_data.get("input_tokens", 0) or 0) + (usage_data.get("output_tokens", 0) or 0),
                    cache_read_tokens=usage_data.get("cached_input_tokens"),
                )

    return AgentResponse(
        agent_type=AgentType.CODEX,
        text="".join(text_parts),
        exit_code=exit_code,
        session_id=session_id,
        usage=usage,
        tool_calls=tool_calls,
        raw_response=raw_events,
        parse_failures=parse_failures,
        parse_failure_samples=parse_failure_samples,
    )
