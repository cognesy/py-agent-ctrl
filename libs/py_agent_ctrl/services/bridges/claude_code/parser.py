from __future__ import annotations

from typing import Any

from py_agent_ctrl.api.events import AgentEvent, AgentResultEvent, AgentTextEvent, AgentToolCallEvent, AgentUnknownEvent
from py_agent_ctrl.api.models import AgentResponse, AgentType, TokenUsage, ToolCall
from py_agent_ctrl.services.bridges.claude_code.models import (
    ClaudeAssistantEvent,
    ClaudeResultEvent,
    ClaudeSystemEvent,
    ClaudeTextContent,
    ClaudeToolResultEvent,
    ClaudeToolUseContent,
    ClaudeUsage,
)


def parse_claude_events(raw: dict[str, Any]) -> list[AgentEvent]:
    event_type = raw.get("type", "")
    if event_type == "system" and raw.get("subtype") == "init":
        ClaudeSystemEvent.model_validate(raw)
        return [AgentUnknownEvent(raw=raw)]

    if event_type == "assistant":
        assistant_event = ClaudeAssistantEvent.model_validate(raw)
        events: list[AgentEvent] = []
        texts = [item.text for item in assistant_event.message.content if isinstance(item, ClaudeTextContent) and item.text]
        if texts:
            events.append(AgentTextEvent(text="".join(texts), raw=raw))
        for item in assistant_event.message.content:
            if isinstance(item, ClaudeToolUseContent):
                events.append(AgentToolCallEvent(
                    tool_call=ToolCall(
                        id=item.id,
                        name=item.name,
                        arguments=item.input,
                        raw=raw,
                    ),
                    raw=raw,
                ))
        return events or [AgentUnknownEvent(raw=raw)]

    if event_type == "tool_result":
        ClaudeToolResultEvent.model_validate(raw)
        return [AgentUnknownEvent(raw=raw)]

    if event_type == "result":
        result_event = ClaudeResultEvent.model_validate(raw)
        return [AgentResultEvent(
            session_id=result_event.session_id or None,
            cost_usd=result_event.cost_usd,
            duration_ms=result_event.duration_ms,
            raw=raw,
        )]

    return [AgentUnknownEvent(raw=raw)]


def parse_claude_event(raw: dict[str, Any]) -> AgentEvent:
    return parse_claude_events(raw)[0]


def _claude_usage_to_token_usage(claude_usage: ClaudeUsage) -> TokenUsage:
    input_tokens = claude_usage.input_tokens or 0
    output_tokens = claude_usage.output_tokens or 0
    cache_read = claude_usage.cache_read_input_tokens or 0
    cache_write = claude_usage.cache_creation_input_tokens or 0
    return TokenUsage(
        input_tokens=claude_usage.input_tokens,
        output_tokens=claude_usage.output_tokens,
        cache_read_tokens=claude_usage.cache_read_input_tokens,
        cache_write_tokens=claude_usage.cache_creation_input_tokens,
        total_tokens=input_tokens + output_tokens + cache_read + cache_write,
    )


def events_to_response(
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
    cost_usd: float | None = None
    duration_ms: int | None = None
    usage: TokenUsage | None = None

    for event in events:
        if isinstance(event, AgentTextEvent):
            text_parts.append(event.text)
        elif isinstance(event, AgentToolCallEvent):
            tool_calls.append(event.tool_call)
        elif isinstance(event, AgentResultEvent):
            session_id = event.session_id or session_id
            cost_usd = event.cost_usd
            duration_ms = event.duration_ms
            if event.raw:
                raw_usage = event.raw.get("usage")
                if isinstance(raw_usage, dict):
                    usage = _claude_usage_to_token_usage(ClaudeUsage.model_validate(raw_usage))

    return AgentResponse(
        agent_type=AgentType.CLAUDE_CODE,
        text="".join(text_parts),
        exit_code=exit_code,
        session_id=session_id,
        cost_usd=cost_usd,
        usage=usage,
        tool_calls=tool_calls,
        raw_response=raw_events,
        parse_failures=parse_failures,
        parse_failure_samples=parse_failure_samples,
        duration_ms=duration_ms,
    )
