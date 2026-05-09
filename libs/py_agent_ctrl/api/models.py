from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Literal
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


class ToolCallStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ToolCallPhase(StrEnum):
    STARTED = "started"
    UPDATED = "updated"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SNAPSHOT = "snapshot"


class ToolKind(StrEnum):
    READ = "read"
    EDIT = "edit"
    DELETE = "delete"
    MOVE = "move"
    SEARCH = "search"
    EXECUTE = "execute"
    THINK = "think"
    FETCH = "fetch"
    OTHER = "other"


class TextContentBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ResourceLinkContentBlock(BaseModel):
    type: Literal["resource_link"] = "resource_link"
    uri: str
    name: str | None = None
    mime_type: str | None = None
    size: int | None = None
    description: str | None = None


class EmbeddedResourceContentBlock(BaseModel):
    type: Literal["resource"] = "resource"
    uri: str
    text: str | None = None
    blob: str | None = None
    mime_type: str | None = None


class ImageContentBlock(BaseModel):
    type: Literal["image"] = "image"
    uri: str | None = None
    data: str | None = None
    mime_type: str | None = None


class DiffContentBlock(BaseModel):
    type: Literal["diff"] = "diff"
    path: str
    new_text: str
    old_text: str | None = None


class TerminalContentBlock(BaseModel):
    type: Literal["terminal"] = "terminal"
    terminal_id: str
    output: str | None = None


type PromptContentBlock = TextContentBlock | ResourceLinkContentBlock | EmbeddedResourceContentBlock | ImageContentBlock
type OutputContentBlock = PromptContentBlock | DiffContentBlock | TerminalContentBlock
type ToolCallContentBlock = OutputContentBlock


def text_block(text: str) -> TextContentBlock:
    return TextContentBlock(text=text)


def resource_link_block(
    uri: str,
    *,
    name: str | None = None,
    mime_type: str | None = None,
    size: int | None = None,
    description: str | None = None,
) -> ResourceLinkContentBlock:
    return ResourceLinkContentBlock(
        uri=uri,
        name=name,
        mime_type=mime_type,
        size=size,
        description=description,
    )


def embedded_text_resource_block(
    uri: str,
    text: str,
    *,
    mime_type: str | None = None,
) -> EmbeddedResourceContentBlock:
    return EmbeddedResourceContentBlock(uri=uri, text=text, mime_type=mime_type)


def embedded_blob_resource_block(
    uri: str,
    blob: str,
    *,
    mime_type: str | None = None,
) -> EmbeddedResourceContentBlock:
    return EmbeddedResourceContentBlock(uri=uri, blob=blob, mime_type=mime_type)


def image_ref_block(uri: str, *, mime_type: str | None = None) -> ImageContentBlock:
    return ImageContentBlock(uri=uri, mime_type=mime_type)


def image_data_block(data: str, *, mime_type: str | None = None) -> ImageContentBlock:
    return ImageContentBlock(data=data, mime_type=mime_type)


def diff_block(path: str, new_text: str, old_text: str | None = None) -> DiffContentBlock:
    return DiffContentBlock(path=path, new_text=new_text, old_text=old_text)


def terminal_ref_block(terminal_id: str, output: str | None = None) -> TerminalContentBlock:
    return TerminalContentBlock(terminal_id=terminal_id, output=output)


def content_blocks_to_text(blocks: Sequence[OutputContentBlock]) -> str:
    return "\n\n".join(_content_block_to_text(block) for block in blocks)


def _content_block_to_text(block: OutputContentBlock) -> str:
    if isinstance(block, TextContentBlock):
        return block.text
    if isinstance(block, ResourceLinkContentBlock):
        name = block.name or block.uri
        return f"[resource: {name}] {block.uri}"
    if isinstance(block, EmbeddedResourceContentBlock):
        if block.text is not None:
            return f"[resource: {block.uri}]\n{block.text}"
        blob_label = block.mime_type or "embedded blob"
        return f"[resource: {block.uri}] <{blob_label}>"
    if isinstance(block, ImageContentBlock):
        if block.uri:
            return f"[image: {block.uri}]"
        data_label = block.mime_type or "embedded image"
        return f"[image: <{data_label}>]"
    if isinstance(block, DiffContentBlock):
        if block.old_text is None:
            return f"[diff: {block.path}]\n{block.new_text}"
        return f"[diff: {block.path}]\n--- old\n{block.old_text}\n+++ new\n{block.new_text}"
    if isinstance(block, TerminalContentBlock):
        if block.output:
            return f"[terminal: {block.terminal_id}]\n{block.output}"
        return f"[terminal: {block.terminal_id}]"
    raise TypeError(f"Unsupported content block: {type(block).__name__}")


def normalize_tool_call_status(status: Any, *, is_error: bool = False) -> ToolCallStatus | None:
    if is_error:
        return ToolCallStatus.FAILED
    if status is None:
        return None
    normalized = str(status).strip().lower().replace("-", "_")
    if normalized in {"queued", "created"}:
        return ToolCallStatus.PENDING
    if normalized in {"running", "started", "inprogress", "in_progress"}:
        return ToolCallStatus.IN_PROGRESS
    if normalized in {"complete", "completed", "success", "succeeded", "ok"}:
        return ToolCallStatus.COMPLETED
    if normalized in {"error", "errored", "failed", "failure"}:
        return ToolCallStatus.FAILED
    if normalized in {"cancelled", "canceled"}:
        return ToolCallStatus.CANCELLED
    return None


def infer_tool_call_phase(status: ToolCallStatus | str | None, *, fallback: ToolCallPhase = ToolCallPhase.SNAPSHOT) -> ToolCallPhase:
    if status is None:
        return fallback
    try:
        normalized_status = ToolCallStatus(status)
    except ValueError:
        return fallback
    if normalized_status is ToolCallStatus.PENDING:
        return ToolCallPhase.STARTED
    if normalized_status is ToolCallStatus.IN_PROGRESS:
        return ToolCallPhase.UPDATED
    if normalized_status is ToolCallStatus.COMPLETED:
        return ToolCallPhase.COMPLETED
    if normalized_status is ToolCallStatus.FAILED:
        return ToolCallPhase.FAILED
    if normalized_status is ToolCallStatus.CANCELLED:
        return ToolCallPhase.CANCELLED
    return fallback


def infer_tool_kind(name: str | None = None, *, event_type: str | None = None) -> ToolKind:
    normalized_name = (name or "").strip().lower().replace("-", "_")
    normalized_event = (event_type or "").strip().lower().replace("-", "_")
    candidates = {normalized_name, normalized_event}
    if candidates & {"read", "read_file", "open", "view"}:
        return ToolKind.READ
    if candidates & {"edit", "write", "write_file", "file_change", "patch", "apply_patch"}:
        return ToolKind.EDIT
    if candidates & {"delete", "remove", "rm"}:
        return ToolKind.DELETE
    if candidates & {"move", "rename", "mv"}:
        return ToolKind.MOVE
    if candidates & {"search", "grep", "ripgrep", "rg", "web_search"}:
        return ToolKind.SEARCH
    if candidates & {"bash", "shell", "command", "command_execution", "execute", "run"}:
        return ToolKind.EXECUTE
    if candidates & {"think", "reasoning", "plan_update"}:
        return ToolKind.THINK
    if candidates & {"fetch", "http", "request", "download"}:
        return ToolKind.FETCH
    return ToolKind.OTHER


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
    kind: ToolKind = ToolKind.OTHER
    arguments: dict[str, Any] = Field(default_factory=dict)
    output: Any = None
    content: list[ToolCallContentBlock] = Field(default_factory=list)
    is_error: bool = False
    status: ToolCallStatus | None = None
    phase: ToolCallPhase | None = None
    raw: dict[str, Any] | None = None


class BridgeCapabilities(BaseModel):
    agent_type: AgentType
    cli_name: str
    supports_streaming: bool = True
    supports_session_resume: bool = True
    supports_continue: bool = True
    supports_permissions: bool = False
    supports_tool_events: bool = False
    supports_usage: bool = False
    supports_reasoning: bool = False
    supports_plan_events: bool = False
    supports_file_change_events: bool = False
    supports_permission_callbacks: bool = False
    supports_cancellation: bool = False
    supports_structured_json_output: bool = False
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
    content: list[PromptContentBlock] = Field(default_factory=list)
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
    content: list[OutputContentBlock] = Field(default_factory=list)
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

    def model_post_init(self, __context: Any) -> None:
        if self.text and not self.content:
            self.content = [text_block(self.text)]

    @property
    def success(self) -> bool:
        return self.exit_code == 0
