"""Typed stream events from Claude Code CLI --output-format stream-json."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextContent:
    text: str


@dataclass
class ToolUseContent:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolResultContent:
    tool_use_id: str
    content: Any
    is_error: bool = False


# ── Event types ──────────────────────────────────────────────────────────────

@dataclass
class SystemInitEvent:
    """First event: session established, tools listed."""
    session_id: str
    tools: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @property
    def type(self) -> str:
        return "system"


@dataclass
class AssistantEvent:
    """Claude's response turn — text and/or tool calls."""
    text_parts: list[TextContent] = field(default_factory=list)
    tool_uses: list[ToolUseContent] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @property
    def type(self) -> str:
        return "assistant"

    @property
    def text(self) -> str:
        return "".join(t.text for t in self.text_parts)


@dataclass
class ToolResultEvent:
    """Claude Code reporting the result of a tool call."""
    tool_use_id: str
    content: Any
    is_error: bool = False
    raw: dict = field(default_factory=dict)

    @property
    def type(self) -> str:
        return "tool_result"


@dataclass
class ResultEvent:
    """Final event — success or error with cost/duration metadata."""
    subtype: str          # "success" | "error_max_turns" | "error_during_execution" | ...
    session_id: str
    result: str           # final text result
    is_error: bool
    cost_usd: float | None
    duration_ms: int | None
    raw: dict = field(default_factory=dict)

    @property
    def type(self) -> str:
        return "result"

    @property
    def success(self) -> bool:
        return self.subtype == "success"


@dataclass
class UnknownEvent:
    raw: dict = field(default_factory=dict)

    @property
    def type(self) -> str:
        return "unknown"


StreamEvent = SystemInitEvent | AssistantEvent | ToolResultEvent | ResultEvent | UnknownEvent


def parse_event(raw: dict) -> StreamEvent:
    """Parse a single decoded JSON object into a typed StreamEvent."""
    event_type = raw.get("type", "")

    if event_type == "system" and raw.get("subtype") == "init":
        raw_tools = raw.get("tools", [])
        tools = [
            t.get("name", "") if isinstance(t, dict) else str(t)
            for t in raw_tools
        ]
        return SystemInitEvent(session_id=raw.get("session_id", ""), tools=tools, raw=raw)

    if event_type == "assistant":
        msg = raw.get("message", {})
        content = msg.get("content", [])
        text_parts = []
        tool_uses = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(TextContent(text=item.get("text", "")))
                elif item.get("type") == "tool_use":
                    tool_uses.append(ToolUseContent(
                        id=item.get("id", ""),
                        name=item.get("name", ""),
                        input=item.get("input", {}),
                    ))
        return AssistantEvent(text_parts=text_parts, tool_uses=tool_uses, raw=raw)

    if event_type == "tool_result":
        return ToolResultEvent(
            tool_use_id=raw.get("tool_use_id", ""),
            content=raw.get("content"),
            is_error=raw.get("is_error", False),
            raw=raw,
        )

    if event_type == "result":
        return ResultEvent(
            subtype=raw.get("subtype", ""),
            session_id=raw.get("session_id", ""),
            result=raw.get("result", ""),
            is_error=raw.get("is_error", False),
            cost_usd=raw.get("cost_usd"),
            duration_ms=raw.get("duration_ms"),
            raw=raw,
        )

    return UnknownEvent(raw=raw)
