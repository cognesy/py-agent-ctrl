from __future__ import annotations

from typing import Any

from py_agent_ctrl.api.events import AgentEvent, AgentResultEvent, AgentTextEvent, AgentUnknownEvent
from py_agent_ctrl.api.models import AgentResponse, AgentType, TokenUsage, ToolCall


def parse_gemini_events(raw: dict[str, Any]) -> list[AgentEvent]:
    event_type = raw.get("type", "")
    if event_type == "init":
        return [AgentResultEvent(session_id=raw.get("session_id"), raw=raw)]
    if event_type == "message" and raw.get("role") == "assistant" and raw.get("delta"):
        return [AgentTextEvent(text=str(raw.get("content", "")), raw=raw)]
    if event_type == "tool_use":
        return [AgentUnknownEvent(raw={"pending_tool": raw})]
    if event_type == "tool_result":
        return [AgentUnknownEvent(raw={"tool_result": raw})]
    if event_type == "result":
        return [AgentResultEvent(raw=raw)]
    return [AgentUnknownEvent(raw=raw)]


def gemini_response_from_output(*, events: list[AgentEvent], raw_events: list[dict[str, Any]], exit_code: int,
                                parse_failures: int, parse_failure_samples: list[str]) -> AgentResponse:
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    session_id: str | None = None
    usage: TokenUsage | None = None
    pending_tools: dict[str, dict[str, Any]] = {}

    for event in events:
        if isinstance(event, AgentTextEvent):
            text_parts.append(event.text)
        elif isinstance(event, AgentResultEvent):
            session_id = event.session_id or session_id
            if event.raw and isinstance(event.raw.get("stats"), dict):
                stats = event.raw["stats"]
                usage = TokenUsage(
                    input_tokens=stats.get("input_tokens"),
                    output_tokens=stats.get("output_tokens"),
                    total_tokens=stats.get("total_tokens"),
                    cache_read_tokens=stats.get("cached"),
                )
        elif isinstance(event, AgentUnknownEvent):
            pending_tool = event.raw.get("pending_tool")
            if isinstance(pending_tool, dict):
                pending_tools[str(pending_tool.get("tool_id", ""))] = pending_tool
            tool_result = event.raw.get("tool_result")
            if isinstance(tool_result, dict):
                tool_id = str(tool_result.get("tool_id", ""))
                tool_use = pending_tools.get(tool_id, {})
                tool_calls.append(ToolCall(
                    id=tool_id,
                    name=str(tool_use.get("tool_name", "")),
                    arguments=dict(tool_use.get("parameters", {})),
                    output=tool_result.get("output") or tool_result.get("error"),
                    is_error=str(tool_result.get("status", "")) == "error",
                    raw=tool_result,
                ))

    return AgentResponse(
        agent_type=AgentType.GEMINI,
        text="".join(text_parts),
        exit_code=exit_code,
        session_id=session_id,
        usage=usage,
        tool_calls=tool_calls,
        raw_response=raw_events,
        parse_failures=parse_failures,
        parse_failure_samples=parse_failure_samples,
    )
