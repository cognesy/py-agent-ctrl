# py-agent-ctrl

Programmatic wrapper for the **Claude Code CLI** — Python port of [cognesy/agent-ctrl](https://github.com/cognesy/agent-ctrl) (PHP).

Zero dependencies beyond the Python standard library.

## Install

```bash
pip install git+https://github.com/cognesy/py-agent-ctrl.git@main
```

## Usage

```python
from agent_ctrl import ClaudeCodeClient

# Simple sync
response = ClaudeCodeClient().execute("Summarise this repo.")
print(response.text)
print(response.session_id)

# With options
response = (
    ClaudeCodeClient()
    .with_system_prompt("You are a code analysis assistant.")
    .with_max_turns(5)
    .with_cwd("/path/to/project")
    .execute("List all API endpoints.")
)

# Session continuity
r1 = ClaudeCodeClient().execute("Start a multi-turn analysis.")
r2 = ClaudeCodeClient().resume(r1.session_id).execute("Now summarise what you found.")

# Async streaming with callbacks
import asyncio

async def main():
    async for event in ClaudeCodeClient().stream("Explain this codebase."):
        from agent_ctrl import AssistantEvent
        if isinstance(event, AssistantEvent):
            print(event.text, end="", flush=True)

asyncio.run(main())
```

## ClaudeCodeClient builder options

| Method | Description |
|--------|-------------|
| `.with_model(model)` | Override the Claude model |
| `.with_system_prompt(text)` | Replace the default system prompt |
| `.append_system_prompt(text)` | Append to the default system prompt |
| `.with_max_turns(n)` | Limit agentic turns |
| `.with_permission_mode(mode)` | `bypassPermissions` (default) / `acceptEdits` / `default` |
| `.with_allowed_tools(*tools)` | Pre-approve specific tools, e.g. `"Read"`, `"Edit"` |
| `.resume(session_id)` | Resume a specific prior session |
| `.continue_session()` | Resume the most recent session |
| `.with_cwd(path)` | Working directory for the subprocess |
| `.with_timeout(seconds)` | Subprocess timeout (default 120s) |
| `.on_text(fn)` | Callback for each text chunk during async streaming |
| `.on_tool_use(fn)` | Callback for each tool use during async streaming |

## ClaudeResponse

| Field | Type | Description |
|-------|------|-------------|
| `text` | `str` | Concatenated assistant text |
| `session_id` | `str \| None` | Session ID for resuming |
| `success` | `bool` | `exit_code == 0 and not is_error` |
| `tool_calls` | `list[ToolUseContent]` | Tools invoked during the run |
| `cost_usd` | `float \| None` | Reported cost (if available) |
| `duration_ms` | `int \| None` | Reported duration (if available) |
| `events` | `list[StreamEvent]` | All raw typed events |

## Requirements

- Python 3.12+
- `claude` CLI installed and on `PATH`: `npm install -g @anthropic-ai/claude-code`
- `ANTHROPIC_API_KEY` set in the environment
