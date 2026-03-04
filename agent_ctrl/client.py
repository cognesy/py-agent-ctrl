"""Claude Code CLI wrapper — Python port of cognesy/agent-ctrl ClaudeCodeBridge.

Zero dependencies beyond the Python standard library.

Usage:
    from agent_ctrl import ClaudeCodeClient

    # Simple sync
    response = ClaudeCodeClient().execute("Summarise this repo.")
    print(response.text, response.session_id)

    # With options
    response = (
        ClaudeCodeClient()
        .with_system_prompt("You are a SAT analysis assistant.")
        .with_max_turns(5)
        .with_cwd("/path/to/project")
        .execute("Analyse assumptions.")
    )

    # Session continuity
    r1 = ClaudeCodeClient().execute("Start.")
    r2 = ClaudeCodeClient().resume(r1.session_id).execute("Continue.")

    # Async streaming
    async for event in ClaudeCodeClient().stream("Analyse..."):
        if isinstance(event, AssistantEvent):
            print(event.text, end="", flush=True)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Callable

from agent_ctrl.events import (
    AssistantEvent,
    ResultEvent,
    StreamEvent,
    ToolUseContent,
    parse_event,
)

log = logging.getLogger(__name__)


# ── Result DTO ────────────────────────────────────────────────────────────────

@dataclass
class ClaudeResponse:
    text: str
    session_id: str | None
    exit_code: int
    is_error: bool
    cost_usd: float | None
    duration_ms: int | None
    tool_calls: list[ToolUseContent]
    events: list[StreamEvent]

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.is_error


# ── Client (fluent builder + executor) ───────────────────────────────────────

class ClaudeCodeClient:
    """Fluent builder and executor for Claude Code CLI subprocess calls.

    Modelled after cognesy/agent-ctrl (PHP) ClaudeCodeBridge + ClaudeCodeBridgeBuilder.
    Always uses --output-format stream-json --verbose for programmatic use.
    """

    def __init__(self) -> None:
        self._model: str | None = None
        self._system_prompt: str | None = None
        self._append_system_prompt: str | None = None
        self._max_turns: int | None = None
        self._permission_mode: str = "bypassPermissions"
        self._allowed_tools: list[str] | None = None
        self._resume_session_id: str | None = None
        self._continue_most_recent: bool = False
        self._add_dirs: list[str] = []
        self._cwd: str | None = None
        self._timeout: int = 120
        self._on_text: Callable[[str], None] | None = None
        self._on_tool_use: Callable[[ToolUseContent], None] | None = None

    # ── Builder methods ───────────────────────────────────────────────────────

    def with_model(self, model: str) -> ClaudeCodeClient:
        self._model = model
        return self

    def with_system_prompt(self, prompt: str) -> ClaudeCodeClient:
        self._system_prompt = prompt
        return self

    def append_system_prompt(self, prompt: str) -> ClaudeCodeClient:
        self._append_system_prompt = prompt
        return self

    def with_max_turns(self, turns: int) -> ClaudeCodeClient:
        self._max_turns = max(1, turns)
        return self

    def with_permission_mode(self, mode: str) -> ClaudeCodeClient:
        """One of: bypassPermissions, acceptEdits, default."""
        self._permission_mode = mode
        return self

    def with_allowed_tools(self, *tools: str) -> ClaudeCodeClient:
        """Pre-approve specific tools. Example: 'Read', 'Edit', 'Bash'."""
        self._allowed_tools = list(tools)
        return self

    def resume(self, session_id: str) -> ClaudeCodeClient:
        """Resume a specific session by ID."""
        self._resume_session_id = session_id
        return self

    def continue_session(self) -> ClaudeCodeClient:
        """Continue the most recent session."""
        self._continue_most_recent = True
        return self

    def with_add_dirs(self, *dirs: str) -> ClaudeCodeClient:
        """Expose additional directories to Claude Code."""
        self._add_dirs = list(dirs)
        return self

    def with_cwd(self, cwd: str | Path) -> ClaudeCodeClient:
        """Set the working directory for the subprocess."""
        self._cwd = str(cwd)
        return self

    def with_timeout(self, seconds: int) -> ClaudeCodeClient:
        self._timeout = seconds
        return self

    def on_text(self, callback: Callable[[str], None]) -> ClaudeCodeClient:
        """Called with each text chunk during async streaming."""
        self._on_text = callback
        return self

    def on_tool_use(self, callback: Callable[[ToolUseContent], None]) -> ClaudeCodeClient:
        """Called for each tool use during async streaming."""
        self._on_tool_use = callback
        return self

    # ── Command building ──────────────────────────────────────────────────────

    def _build_argv(self, prompt: str) -> list[str]:
        """Construct the full argv for `claude` CLI invocation."""
        claude = _find_claude()
        argv: list[str] = []

        # Prepend stdbuf on Linux/macOS to disable output buffering
        if shutil.which("stdbuf"):
            argv = ["stdbuf", "-o0"]

        argv += [claude, "-p", prompt]

        # Session flags (mutually exclusive)
        if self._continue_most_recent:
            argv.append("--continue")
        elif self._resume_session_id:
            argv += ["--resume", self._resume_session_id]

        # Always stream-json + verbose for reliable programmatic output
        argv += ["--output-format", "stream-json", "--verbose"]

        # Permission mode
        if self._permission_mode != "default":
            argv += ["--permission-mode", self._permission_mode]

        # Pre-approve specific tools
        if self._allowed_tools:
            argv += ["--allowedTools", ",".join(self._allowed_tools)]

        if self._max_turns is not None:
            argv += ["--max-turns", str(self._max_turns)]

        if self._model:
            argv += ["--model", self._model]

        if self._system_prompt:
            argv += ["--system-prompt", self._system_prompt]
        elif self._append_system_prompt:
            argv += ["--append-system-prompt", self._append_system_prompt]

        for d in self._add_dirs:
            argv += ["--add-dir", d]

        return argv

    # ── Sync execution ────────────────────────────────────────────────────────

    def execute(self, prompt: str) -> ClaudeResponse:
        """Run Claude Code and block until completion."""
        argv = self._build_argv(prompt)
        log.debug("agent_ctrl execute argv=%s", argv[:4])

        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=self._timeout,
            cwd=self._cwd,
            env=_clean_env(),
        )
        return _parse_stdout(result.stdout, result.returncode)

    # ── Async streaming ───────────────────────────────────────────────────────

    async def stream(self, prompt: str) -> AsyncIterator[StreamEvent]:
        """Async generator yielding typed StreamEvents as they arrive."""
        argv = self._build_argv(prompt)
        log.debug("agent_ctrl stream argv=%s", argv[:4])

        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._cwd,
            env=_clean_env(),
        )

        assert process.stdout is not None
        async for raw_line in process.stdout:
            line = raw_line.decode().strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            event = parse_event(data)

            if isinstance(event, AssistantEvent) and self._on_text:
                for tp in event.text_parts:
                    self._on_text(tp.text)
            if isinstance(event, AssistantEvent) and self._on_tool_use:
                for tu in event.tool_uses:
                    self._on_tool_use(tu)

            yield event

        await process.wait()

    async def execute_async(self, prompt: str) -> ClaudeResponse:
        """Async version of execute() — collects all events then returns."""
        all_events: list[StreamEvent] = []
        async for event in self.stream(prompt):
            all_events.append(event)
        return _events_to_response(all_events, exit_code=0)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_claude() -> str:
    claude = shutil.which("claude")
    if claude is None:
        raise RuntimeError(
            "claude CLI not found on PATH. "
            "Install: npm install -g @anthropic-ai/claude-code"
        )
    return claude


def _clean_env() -> dict[str, str]:
    """Strip Claude Code nesting-guard env vars.

    Claude Code sets CLAUDECODE (and variants) to prevent nested sessions.
    Remove them when spawning a subprocess intentionally.
    """
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("CLAUDECODE") or key.startswith("CLAUDE_CODE"):
            del env[key]
    return env


def _parse_stdout(stdout: str, exit_code: int) -> ClaudeResponse:
    events: list[StreamEvent] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(parse_event(data))
    return _events_to_response(events, exit_code)


def _events_to_response(events: list[StreamEvent], exit_code: int) -> ClaudeResponse:
    text_parts: list[str] = []
    tool_calls: list[ToolUseContent] = []
    session_id: str | None = None
    is_error = False
    cost_usd: float | None = None
    duration_ms: int | None = None

    for event in events:
        if isinstance(event, AssistantEvent):
            text_parts.append(event.text)
            tool_calls.extend(event.tool_uses)
        elif isinstance(event, ResultEvent):
            session_id = event.session_id or session_id
            is_error = event.is_error
            cost_usd = event.cost_usd
            duration_ms = event.duration_ms

    return ClaudeResponse(
        text="".join(text_parts),
        session_id=session_id,
        exit_code=exit_code,
        is_error=is_error,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
        tool_calls=tool_calls,
        events=events,
    )
