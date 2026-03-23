# Migration

This repo no longer preserves the old flat Claude-only package layout.

## Import Change

Before:

```python
from agent_ctrl import ClaudeCodeClient
```

After:

```python
from py_agent_ctrl import AgentCtrl
```

## Execution Change

Before:

```python
response = ClaudeCodeClient().execute("Summarize this repository.")
```

After:

```python
response = AgentCtrl.claude_code().execute("Summarize this repository.")
```

## Session Change

Before:

```python
response = ClaudeCodeClient().resume(session_id).execute("Continue.")
```

After:

```python
response = AgentCtrl.claude_code().resume_session(session_id).execute("Continue.")
```

## Directory Change

Before:

```python
ClaudeCodeClient().with_cwd(repo_path).execute(prompt)
```

After:

```python
AgentCtrl.claude_code().in_directory(repo_path).execute(prompt)
```

## Additional Directories

Before:

```python
ClaudeCodeClient().with_add_dirs("/shared/a", "/shared/b")
```

After:

```python
AgentCtrl.claude_code().with_additional_dirs(["/shared/a", "/shared/b"])
```

## Package Layout

Before:

- `./agent_ctrl`
- flat Claude-specific DTOs and parser helpers

After:

- `./apps`
- `./libs/py_agent_ctrl`
- `./resources`
- `./docs`
- `./tests`
