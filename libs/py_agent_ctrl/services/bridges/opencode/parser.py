from __future__ import annotations

from typing import Any

from py_agent_ctrl.api.events import AgentEvent, AgentResultEvent, AgentTextEvent, AgentToolCallEvent, AgentUnknownEvent
from py_agent_ctrl.api.models import AgentResponse, AgentType, TokenUsage, ToolCall


def parse_opencode_events(raw: dict[str, Any]) -> list[AgentEvent]:
    event_type = raw.get("type", "")
    if event_type == "text":
        part = raw.get("part", {})
        return [AgentTextEvent(text=str(part.get("text", "")), raw=raw)]
    if event_type == "tool_use":
        part = raw.get("part", {})
        state = part.get("state", {})
        return [AgentToolCallEvent(tool_call=ToolCall(
            id=part.get("callID"),
            name=str(part.get("tool", "")),
            arguments=dict(state.get("input", {})),
            output=state.get("output"),
            is_error=str(state.get("status", "")) in {"error", "failed"},
            status=state.get("status"),
            raw=raw,
        ), raw=raw)]
    if event_type == "step_finish":
        return [AgentResultEvent(session_id=raw.get("sessionID"), cost_usd=float(raw.get("part", {}).get("cost", 0) or 0), raw=raw)]
    return [AgentUnknownEvent(raw=raw)]


def opencode_response_from_output(*, events: list[AgentEvent], raw_events: list[dict[str, Any]], exit_code: int,
                                  parse_failures: int, parse_failure_samples: list[str]) -> AgentResponse:
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    session_id: str | None = None
    usage: TokenUsage | None = None
    total_cost = 0.0

    for event in events:
        if isinstance(event, AgentTextEvent):
            text_parts.append(event.text)
        elif isinstance(event, AgentToolCallEvent):
            tool_calls.append(event.tool_call)
        elif isinstance(event, AgentResultEvent):
            session_id = event.session_id or session_id
            total_cost += event.cost_usd or 0.0
            tokens = event.raw.get("part", {}).get("tokens", {}) if event.raw else {}
            cache = tokens.get("cache", {}) if isinstance(tokens, dict) else {}
            if isinstance(tokens, dict) and tokens:
                usage = TokenUsage(
                    input_tokens=tokens.get("input"),
                    output_tokens=tokens.get("output"),
                    reasoning_tokens=tokens.get("reasoning"),
                    cache_read_tokens=cache.get("read"),
                    cache_write_tokens=cache.get("write"),
                    total_tokens=sum(int(tokens.get(key, 0) or 0) for key in ("input", "output", "reasoning"))
                    + int(cache.get("read", 0) or 0)
                    + int(cache.get("write", 0) or 0),
                )

    return AgentResponse(
        agent_type=AgentType.OPENCODE,
        text="".join(text_parts),
        exit_code=exit_code,
        session_id=session_id,
        usage=usage,
        cost_usd=total_cost or None,
        tool_calls=tool_calls,
        raw_response=raw_events,
        parse_failures=parse_failures,
        parse_failure_samples=parse_failure_samples,
    )
