---
name: upgrade
description: Upgrade downstream code from the old Claude-only py-agent-ctrl API to the new CLI-bridge architecture with a clean-cut new repo layout and normalized Pydantic models.
---

# Upgrade Skill

Use this skill when migrating existing client code that depends on the older
`py-agent-ctrl` package layout or its Claude-only API.

Read [docs/dev/architecture.md](../../../docs/dev/architecture.md) first. That
document defines the target layout, bridge inventory, and migration direction.

## Scope

This skill assumes:

- the target repo uses CLI coding agents only
- `py-agent-ctrl` now separates direct CLI bridges from the common adapter API
- structured models are Pydantic models
- the preferred public entry point is the common facade
- the legacy flat package layout is removed rather than preserved in parallel

## Upgrade Goal

Move client code from:

- flat imports
- Claude-only assumptions
- direct dependence on provider parsing details

to:

- facade-based agent selection
- normalized request/response/event models
- provider-specific adapters only where truly needed

## Default Migration Strategy

1. Find old imports and usage sites.
2. Classify each usage as either common or provider-specific.
3. Migrate common usage to the normalized facade first.
4. Keep provider-specific code on the provider adapter only when the feature is
   not portable.
5. Preserve behavior before expanding to other agents.

Use fast search:

```bash
rg -n "ClaudeCodeClient|ClaudeResponse|parse_event|AssistantEvent|ToolUseContent|resume\\(" .
```

## What Counts As Common Usage

These cases should migrate to the common adapter API:

- execute a prompt
- stream text output
- inspect normalized tool calls
- continue or resume a session
- set timeout
- set working directory
- read normalized response text, session ID, execution ID, usage, or cost

These cases stay provider-specific until the common API explicitly supports
them:

- Claude permission modes
- Codex sandbox and image input
- OpenCode session sharing and named agents
- Pi skills, extensions, and tool allowlists
- Gemini policy files, MCP allowlists, and approval modes

## Import Mapping

Prefer this style after migration:

```python
from py_agent_ctrl import AgentCtrl
```

Legacy Claude-only style to replace:

```python
from agent_ctrl import ClaudeCodeClient
```

Portable replacement:

```python
response = AgentCtrl.claude_code().execute("Summarize this repository.")
```

If the client is no longer Claude-specific, switch the provider at the facade:

```python
response = AgentCtrl.codex().execute("Write a refactoring plan.")
```

## Common Rewrite Patterns

### Basic Execution

Before:

```python
from agent_ctrl import ClaudeCodeClient

response = ClaudeCodeClient().execute("Summarize this repository.")
print(response.text)
```

After:

```python
from py_agent_ctrl import AgentCtrl

response = AgentCtrl.claude_code().execute("Summarize this repository.")
print(response.text)
```

### Resume And Continue

Before:

```python
client = ClaudeCodeClient().resume(session_id)
response = client.execute("Continue.")
```

After:

```python
response = (
    AgentCtrl.claude_code()
    .resume_session(session_id)
    .execute("Continue.")
)
```

### Working Directory

Before:

```python
ClaudeCodeClient().with_cwd(repo_path).execute(prompt)
```

After:

```python
AgentCtrl.claude_code().in_directory(repo_path).execute(prompt)
```

### Additional Directories

Before:

```python
ClaudeCodeClient().with_add_dirs("/shared/a", "/shared/b")
```

After:

```python
AgentCtrl.claude_code().with_additional_dirs(["/shared/a", "/shared/b"])
```

## Response Migration Rules

Client code should depend on normalized response fields wherever possible:

- `response.text`
- `response.execution_id`
- `response.session_id`
- `response.exit_code`
- `response.success`
- `response.tool_calls`
- `response.usage`
- `response.cost_usd`

Do not keep client code coupled to raw provider event payloads unless there is a
clear provider-specific requirement.

## Event Migration Rules

If client code only needs text and tool activity, migrate to normalized events.

Avoid locking downstream code to removed legacy parser helpers such as:

- `parse_event`
- flat dataclass event types under `agent_ctrl.events`

Prefer the normalized event surface exposed by the adapter layer.

## Provider-Specific Rule

Use the common facade by default.

Drop to the provider adapter only when the downstream code requires a provider
feature that is not portable. Examples:

- Claude-specific permission modes
- Codex-specific sandbox or image input
- Pi-specific skill loading
- Gemini-specific MCP restrictions

When you need provider-specific options, keep the response normalized.

## Test Migration

When upgrading a client repo, split tests by intent:

- `tests/unit/` for request building, event normalization, and small adapters
- `tests/integration/` for real CLI subprocess execution
- `tests/feature/` for end-to-end user-visible flows
- `tests/regression/` for frozen stream payload and migration regressions

## Python Tooling Rule

Use `uv` only when you need to run Python-based validation in this project.

Examples:

```bash
uv run pytest
uv run pytest tests/unit
uv run ruff check .
```

Do not recommend `python`, `python3`, `pip`, or `pip3`.

## Decision Rule

When uncertain, choose the migration that reduces provider coupling:

- first choice: common facade + common response models
- second choice: provider adapter + common response models
- last choice: provider raw bridge details

The canonical Python import root after migration is `py_agent_ctrl`. Legacy
examples that import from `agent_ctrl` are search targets to replace, not APIs
to preserve.

The direct bridge exists to isolate CLI specifics. Client code should usually
not need to know those details.
