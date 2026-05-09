# ctrlagent CLI

`ctrlagent` is the thin command-layer shell over the same action layer used by the Python API.

`agents list` and `agents capabilities` are safe local metadata commands.
`execute`, `stream`, `resume`, and `continue` invoke external provider CLIs, so
the selected CLI must be installed and authenticated first.

## List Agents

```bash
uv run ctrlagent agents list
```

## Show Capabilities

```bash
uv run ctrlagent agents capabilities --agent codex
```

## Execute

```bash
uv run ctrlagent execute --agent claude-code "Summarize this repository."
```

## Stream

```bash
uv run ctrlagent stream --agent gemini "Explain the architecture."
```

## Resume

```bash
uv run ctrlagent resume --agent codex --session thread_123 "Continue."
```

## Continue Most Recent

```bash
uv run ctrlagent continue --agent pi "Proceed."
```

## Supported Agent Names

- `claude-code`
- `codex`
- `opencode`
- `pi`
- `gemini`
