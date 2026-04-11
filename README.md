# py-agent-ctrl

Unified Python bridge for CLI coding agents.

This repo exposes:

- a Python API under `py_agent_ctrl`
- a unified `ctrlagent` CLI
- direct CLI bridges for `claude`, `codex`, `opencode`, `pi`, and `gemini`

The codebase follows the clean layout described in [docs/dev/architecture.md](docs/dev/architecture.md):

- `apps/` for runnable shells
- `libs/` for importable code
- `resources/` for passive assets
- `docs/` for documentation
- `tests/` for unit, integration, feature, and regression coverage

## Development

Use `uv` only:

```bash
uv sync --extra dev
uv run pytest tests/unit tests/integration tests/feature tests/regression
uv run ctrlagent agents list
```

## Python API

### Execute (blocking)

```python
from py_agent_ctrl import AgentCtrl

response = (
    AgentCtrl.claude_code()
    .with_model("claude-sonnet-4-5")
    .with_permission_mode("bypassPermissions")
    .execute("Summarize this repository.")
)

print(response.text)
print(response.session_id)
print(response.usage)       # TokenUsage with input/output/cache tokens
print(response.tool_calls)  # list[ToolCall]
```

### Stream (real-time)

```python
from py_agent_ctrl import AgentCtrl, AgentReasoningEvent, AgentTextEvent, AgentToolCallEvent

result = AgentCtrl.gemini().yolo().stream("Explain the architecture.")

for event in result:
    if isinstance(event, AgentTextEvent):
        print(event.text, end="", flush=True)
    elif isinstance(event, AgentReasoningEvent):
        print(f"\n[reasoning] {event.text}")
    elif isinstance(event, AgentToolCallEvent):
        print(f"\n[tool: {event.tool_call.name}]")

print(f"\nexit code: {result.exit_code}")
```

Streams may also emit richer normalized events such as `AgentPlanUpdateEvent`,
`AgentUsageEvent`, `AgentWarningEvent`, and `AgentFileChangeEvent` when a
provider exposes that information.

### Other bridges

```python
from py_agent_ctrl import AgentCtrl

AgentCtrl.make("codex").execute("Review the tests.")
AgentCtrl.codex().with_sandbox("workspace-write").execute("Review the tests.")
AgentCtrl.open_code().with_agent("coder").execute("Refactor the payment flow.")
AgentCtrl.pi().with_thinking("high").execute("Create an implementation plan.")
AgentCtrl.gemini().plan_mode().execute("Inspect the architecture.")
```

### Callbacks and wiretaps

```python
from py_agent_ctrl import AgentCtrl

response = (
    AgentCtrl.codex()
    .on_text(lambda text: print(text, end=""))
    .on_tool_call(lambda tool_call: print(f"\n[tool: {tool_call.name}]"))
    .on_complete(lambda response: print(f"\nexit code: {response.exit_code}"))
    .execute("Summarize this repository.")
)
```

For streaming responses, `on_text` receives deduplicated text deltas. The
underlying `stream(...)` iterator still yields the original normalized events,
and `on_event` sees those original events before text-specific filtering.

### Error handling

```python
from py_agent_ctrl import AgentCtrl, BinaryNotFoundError, ProcessTimeoutError

try:
    response = AgentCtrl.claude_code().execute("Hello.")
except BinaryNotFoundError as e:
    print(f"Install the agent first: {e.install_hint}")
```

The core error taxonomy also includes `AgentExecutionError`,
`WorkingDirectoryNotFoundError`, `ProcessStartError`, `ProcessTimeoutError`,
`ProcessFailedError`, `JsonDecodeFailureError`, and
`ProviderParseFailureError`. Current bridge execution returns normalized
`AgentResponse` / `ProcessOutput` diagnostics where possible and keeps
`BinaryNotFoundError` for binary preflight failures.

## CLI

```bash
uv run ctrlagent agents list
uv run ctrlagent agents capabilities --agent claude-code
uv run ctrlagent execute --agent claude-code "Summarize this repository."
uv run ctrlagent stream --agent gemini "Explain the architecture."
uv run ctrlagent resume --agent codex --session thread_123 "Continue."
uv run ctrlagent continue --agent gemini "Proceed."
```

## Supported Agents

| Agent | Python Facade | CLI Name |
|-------|---------------|----------|
| Claude Code | `AgentCtrl.claude_code()` | `claude-code` |
| Codex | `AgentCtrl.codex()` | `codex` |
| OpenCode | `AgentCtrl.opencode()` / `AgentCtrl.open_code()` | `opencode` |
| Pi | `AgentCtrl.pi()` | `pi` |
| Gemini | `AgentCtrl.gemini()` | `gemini` |

## Migration

This repo is a clean cut from the old flat Claude-only layout.

- old root package: `agent_ctrl`
- new root package: `py_agent_ctrl`
- old client: `ClaudeCodeClient`
- new entrypoint: `AgentCtrl`

See:

- [docs/user/quickstart.md](docs/user/quickstart.md)
- [docs/user/cli.md](docs/user/cli.md)
- [docs/user/migration.md](docs/user/migration.md)
- [resources/skills/upgrade/SKILL.md](resources/skills/upgrade/SKILL.md)
