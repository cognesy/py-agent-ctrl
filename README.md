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
from py_agent_ctrl import AgentCtrl, AgentTextEvent, AgentToolCallEvent

result = AgentCtrl.gemini().yolo().stream("Explain the architecture.")

for event in result:
    if isinstance(event, AgentTextEvent):
        print(event.text, end="", flush=True)
    elif isinstance(event, AgentToolCallEvent):
        print(f"\n[tool: {event.tool_call.name}]")

print(f"\nexit code: {result.exit_code}")
```

### Other bridges

```python
from py_agent_ctrl import AgentCtrl

AgentCtrl.codex().with_sandbox("workspace-write").execute("Review the tests.")
AgentCtrl.opencode().with_agent("coder").execute("Refactor the payment flow.")
AgentCtrl.pi().with_thinking("high").execute("Create an implementation plan.")
AgentCtrl.gemini().plan_mode().execute("Inspect the architecture.")
```

### Error handling

```python
from py_agent_ctrl import AgentCtrl, BinaryNotFoundError

try:
    response = AgentCtrl.claude_code().execute("Hello.")
except BinaryNotFoundError as e:
    print(f"Install the agent first: {e.install_hint}")
```

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
| OpenCode | `AgentCtrl.opencode()` | `opencode` |
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
