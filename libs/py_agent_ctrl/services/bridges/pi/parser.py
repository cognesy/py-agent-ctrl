from __future__ import annotations

from typing import Any

from py_agent_ctrl.api.events import AgentEvent, AgentResultEvent, AgentTextEvent, AgentToolCallEvent, AgentUnknownEvent
from py_agent_ctrl.api.models import AgentResponse, AgentType, TokenUsage, ToolCall


def parse_pi_events(raw: dict[str, Any]) -> list[AgentEvent]:
    event_type = raw.get("type", "")
    if event_type == "session":
        return [AgentResultEvent(session_id=raw.get("id"), raw=raw)]
    if event_type == "message_update":
        assistant_event = raw.get("assistantMessageEvent", {})
        if assistant_event.get("type") == "text_delta":
            return [AgentTextEvent(text=str(assistant_event.get("delta", "")), raw=raw)]
    if event_type == "tool_execution_end":
        return [AgentToolCallEvent(tool_call=ToolCall(
            id=raw.get("toolCallId"),
            name=str(raw.get("toolName", "")),
            arguments={},
            output=raw.get("result"),
            is_error=bool(raw.get("isError", False)),
            raw=raw,
        ), raw=raw)]
    if event_type == "message_end":
        return [AgentResultEvent(raw=raw)]
    return [AgentUnknownEvent(raw=raw)]


def pi_response_from_output(*, events: list[AgentEvent], raw_events: list[dict[str, Any]], exit_code: int,
                            parse_failures: int, parse_failure_samples: list[str]) -> AgentResponse:
    text_parts: list[str] = []
    final_assistant_text: str | None = None
    tool_calls: list[ToolCall] = []
    session_id: str | None = None
    usage: TokenUsage | None = None
    cost_usd: float | None = None

    for event in events:
        if isinstance(event, AgentTextEvent):
            text_parts.append(event.text)
        elif isinstance(event, AgentToolCallEvent):
            tool_calls.append(event.tool_call)
        elif isinstance(event, AgentResultEvent):
            session_id = event.session_id or session_id
            message = event.raw.get("message", {}) if event.raw else {}
            if isinstance(message, dict):
                role = message.get("role")
                usage_data = message.get("usage")
                if isinstance(usage_data, dict):
                    usage = TokenUsage(
                        input_tokens=usage_data.get("input"),
                        output_tokens=usage_data.get("output"),
                        cache_read_tokens=usage_data.get("cacheRead"),
                        cache_write_tokens=usage_data.get("cacheWrite"),
                        total_tokens=usage_data.get("totalTokens"),
                    )
                    cost = usage_data.get("cost")
                    if isinstance(cost, dict):
                        cost_usd = cost.get("total")
                if role == "assistant":
                    assistant_parts: list[str] = []
                    for part in message.get("content", []):
                        if isinstance(part, dict) and part.get("type") == "text":
                            assistant_parts.append(str(part.get("text", "")))
                    if assistant_parts:
                        final_assistant_text = "".join(assistant_parts)

    text = "".join(text_parts)
    if final_assistant_text:
        if not text:
            text = final_assistant_text
        elif final_assistant_text.startswith(text):
            text = final_assistant_text
        elif text.endswith(final_assistant_text):
            pass
        else:
            text = f"{text}{final_assistant_text}"

    return AgentResponse(
        agent_type=AgentType.PI,
        text=text,
        exit_code=exit_code,
        session_id=session_id,
        usage=usage,
        cost_usd=cost_usd,
        tool_calls=tool_calls,
        raw_response=raw_events,
        parse_failures=parse_failures,
        parse_failure_samples=parse_failure_samples,
    )
