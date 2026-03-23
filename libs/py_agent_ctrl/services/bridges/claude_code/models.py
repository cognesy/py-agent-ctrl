from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ClaudeTextContent(BaseModel):
    type: str = "text"
    text: str = ""


class ClaudeToolUseContent(BaseModel):
    type: str = "tool_use"
    id: str = ""
    name: str = ""
    input: dict[str, Any] = Field(default_factory=dict)


class ClaudeAssistantMessage(BaseModel):
    role: str = "assistant"
    content: list[ClaudeTextContent | ClaudeToolUseContent] = Field(default_factory=list)


class ClaudeSystemEvent(BaseModel):
    type: str = "system"
    subtype: str = "init"
    session_id: str = ""
    tools: list[dict[str, Any] | str] = Field(default_factory=list)


class ClaudeAssistantEvent(BaseModel):
    type: str = "assistant"
    message: ClaudeAssistantMessage = Field(default_factory=ClaudeAssistantMessage)


class ClaudeToolResultEvent(BaseModel):
    type: str = "tool_result"
    tool_use_id: str = ""
    content: Any = None
    is_error: bool = False


class ClaudeUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None


class ClaudeResultEvent(BaseModel):
    type: str = "result"
    subtype: str = ""
    session_id: str = ""
    result: str = ""
    is_error: bool = False
    cost_usd: float | None = None
    duration_ms: int | None = None
    usage: ClaudeUsage | None = None
