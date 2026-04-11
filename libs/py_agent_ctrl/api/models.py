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


class SessionOperation(StrEnum):
    RESUME = "resume"
    CONTINUE = "continue"
    LIST = "list"
    LOAD = "load"
    FORK = "fork"
    TAG = "tag"
    RENAME = "rename"
    DELETE = "delete"


class PermissionOptionKind(StrEnum):
    ALLOW_ONCE = "allow_once"
    ALLOW_ALWAYS = "allow_always"
    REJECT_ONCE = "reject_once"
    REJECT_ALWAYS = "reject_always"
    ABORT = "abort"


class PermissionOutcome(StrEnum):
    SELECTED = "selected"
    CANCELLED = "cancelled"


class SandboxDriver(StrEnum):
    HOST = "host"
    DOCKER = "docker"
    PODMAN = "podman"
    FIREJAIL = "firejail"
    BUBBLEWRAP = "bubblewrap"


class ClaudePermissionMode(StrEnum):
    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    PLAN = "plan"
    BYPASS_PERMISSIONS = "bypassPermissions"
    DONT_ASK = "dontAsk"
    AUTO = "auto"


class CodexSandboxMode(StrEnum):
    READ_ONLY = "read-only"
    WORKSPACE_WRITE = "workspace-write"
    DANGER_FULL_ACCESS = "danger-full-access"


class GeminiApprovalMode(StrEnum):
    DEFAULT = "default"
    AUTO_EDIT = "auto_edit"
    YOLO = "yolo"
    PLAN = "plan"


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
    supports_permissions: bool = False
    supported_options: list[str] = Field(default_factory=list)


class SessionCapabilities(BaseModel):
    can_resume: bool = False
    can_continue: bool = False
    can_list: bool = False
    can_load: bool = False
    can_fork: bool = False
    can_tag: bool = False
    can_rename: bool = False
    can_delete: bool = False


class AgentRequest(BaseModel):
    prompt: str
    model: str | None = None
    system_prompt: str | None = None
    append_system_prompt: str | None = None
    max_turns: int | None = None
    working_directory: str | None = None
    additional_directories: list[str] = Field(default_factory=list)
    timeout_seconds: int = 120
    sandbox_driver: SandboxDriver = SandboxDriver.HOST
    resume_session_id: str | None = None
    continue_session: bool = False
    provider_options: dict[str, Any] = Field(default_factory=dict)


class SessionInfo(BaseModel):
    agent_type: AgentType
    session_id: str
    execution_id: str | None = None
    title: str | None = None
    cwd: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    raw: Any = None


class PermissionOption(BaseModel):
    option_id: str
    name: str
    kind: PermissionOptionKind


class PermissionRequest(BaseModel):
    id: str
    agent_type: AgentType
    tool_call_id: str
    execution_id: str | None = None
    session_id: str | None = None
    tool_name: str | None = None
    title: str | None = None
    kind: str | None = None
    raw_input: Any = None
    raw_output: Any = None
    options: list[PermissionOption] = Field(default_factory=list)


class PermissionResponse(BaseModel):
    outcome: PermissionOutcome
    option_id: str | None = None

    @classmethod
    def selected(cls, option_id: str) -> PermissionResponse:
        return cls(outcome=PermissionOutcome.SELECTED, option_id=option_id)

    @classmethod
    def cancelled(cls) -> PermissionResponse:
        return cls(outcome=PermissionOutcome.CANCELLED)


class ClaudeCodeProviderOptions(BaseModel):
    permission_mode: ClaudePermissionMode | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    disallowed_tools: list[str] = Field(default_factory=list)
    settings: str | None = None
    mcp_config: str | None = None


class CodexProviderOptions(BaseModel):
    sandbox: CodexSandboxMode | None = None
    full_auto: bool = False
    dangerously_bypass: bool = False
    skip_git_repo_check: bool = False
    images: list[str] = Field(default_factory=list)
    config_overrides: dict[str, Any] = Field(default_factory=dict)


class GeminiProviderOptions(BaseModel):
    approval_mode: GeminiApprovalMode | None = None
    sandbox: bool = False
    include_directories: list[str] = Field(default_factory=list)
    extensions: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_mcp_servers: list[str] = Field(default_factory=list)
    policy_files: list[str] = Field(default_factory=list)
    debug: bool = False


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
