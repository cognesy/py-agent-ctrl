from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentType(StrEnum):
    CLAUDE_CODE = "claude-code"
    CODEX = "codex"
    OPENCODE = "opencode"
    PI = "pi"
    GEMINI = "gemini"


class TokenUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    reasoning_tokens: int | None = None


class ToolCall(BaseModel):
    id: str | None = None
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    output: Any = None
    is_error: bool = False
    status: str | None = None
    raw: dict[str, Any] | None = None


class BridgeCapabilities(BaseModel):
    agent_type: AgentType
    cli_name: str
    supports_streaming: bool = True
    supports_session_resume: bool = True
    supports_continue: bool = True
    supported_options: list[str] = Field(default_factory=list)


class AgentRequest(BaseModel):
    prompt: str
    model: str | None = None
    system_prompt: str | None = None
    append_system_prompt: str | None = None
    max_turns: int | None = None
    working_directory: str | None = None
    additional_directories: list[str] = Field(default_factory=list)
    timeout_seconds: int = 120
    resume_session_id: str | None = None
    continue_session: bool = False
    provider_options: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    agent_type: AgentType
    text: str = ""
    exit_code: int = 0
    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str | None = None
    usage: TokenUsage | None = None
    cost_usd: float | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    raw_response: Any = None
    parse_failures: int = 0
    parse_failure_samples: list[str] = Field(default_factory=list)
    duration_ms: int | None = None

    @property
    def success(self) -> bool:
        return self.exit_code == 0
