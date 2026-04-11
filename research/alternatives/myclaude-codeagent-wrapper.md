# myclaude codeagent-wrapper

Local reference:
`/Users/ddebowczyk/projects/_ext/myclaude/codeagent-wrapper`

## Fit

This is the closest direct CLI abstraction reference. It wraps multiple backend
CLIs behind one wrapper binary and avoids a long-running HTTP API. It is still
workflow-oriented, not a Python library, but its internal shape maps well to
`py-agent-ctrl`.

## Relevant Design

Backend contract:

- `internal/backend/backend.go` defines a small `Backend` interface:
  `Name()`, `Command()`, `BuildArgs(...)`, and `Env(...)`.
- `internal/backend/registry.go` selects backends by normalized name.
- Provider implementations keep target-native CLI details in separate files:
  `codex.go`, `claude.go`, `gemini.go`, `opencode.go`.

Configuration:

- `internal/config/config.go` separates wrapper-level fields from backend
  behavior: mode, task, session ID, workdir, model, reasoning effort, backend,
  agent preset, prompt file, skip-permissions/yolo, tools, skills, worktree, and
  parallel worker limits.
- `internal/config/agent.go` supports named agent presets in
  `~/.codeagent/models.json`, per-backend base URL/API key, dynamic agents under
  `~/.codeagent/agents/{name}.md`, and safe agent-name validation.

Prompt and context injection:

- `internal/executor/stdin.go` switches to stdin for piped input, long tasks, or
  shell-sensitive characters.
- `internal/executor/prompt.go` validates prompt-file paths, follows symlink
  safety checks, wraps agent prompts in explicit tags, detects project tech stack,
  and budgets injected skill content.

Execution hardening:

- `internal/executor/executor.go` starts the JSON parser goroutine before the
  subprocess to avoid missing fast output.
- It tracks stdout/stderr separately, captures a bounded stderr tail, filters
  known noisy stderr patterns, logs raw backend output, and preserves parsed
  output even on non-zero exit when possible.
- It handles context timeout and SIGINT/SIGTERM, sends graceful termination, then
  force-kills if needed.
- It closes pipes with explicit reasons and drains stdout/stderr to avoid
  goroutine/process deadlocks.
- It injects backend env vars while masking API keys in logs.
- It unsets `CLAUDECODE` and isolates nested `CLAUDE_CODE_TMPDIR` to avoid
  Claude nested-session failures.

Parsing:

- `internal/parser/parser.go` detects backend event dialects by shape and parses
  Codex, Claude, Gemini, and OpenCode JSON streams in one pass.
- It caps JSON line size, truncates warnings, and preserves a thread/session ID.

Parallelism and isolation:

- `internal/executor/parallel_config.go` parses a simple task format with IDs,
  dependencies, backend, model, agent, skills, and worktree options.
- `TopologicalSort` and `ExecuteConcurrentWithContext` execute dependency
  layers with bounded worker concurrency and skip downstream tasks after failed
  dependencies.
- `internal/worktree/worktree.go` creates per-task git worktrees with generated
  branch names.

Reporting:

- `internal/app/output_file.go` can write structured JSON output.
- `GenerateFinalOutputWithMode` produces a compact execution report with
  successful tasks, files/tests/coverage, failure details, and log paths.

## What To Borrow

- Add a `CommandSpec` / `CommandExecutor` layer instead of letting every bridge
  call `subprocess.run` directly.
- Move provider env construction into provider-specific command builders.
- Preserve the distinction between wrapper-common settings and provider-native
  options.
- Add stdin heuristics for long/multiline/shell-sensitive prompts.
- Add stderr tail capture to normalized failures.
- Add graceful termination, forced kill, and pipe-drain behavior for streaming.
- Add prompt-file/path validation before any future prompt-file API.
- Consider optional worktree execution as a first-class isolation feature, not a
  hack in one provider.
- Treat parallel execution as a separate orchestration layer over the same bridge
  primitives, not as part of individual provider bridges.

## What Not To Copy Directly

- Defaulting Codex to sandbox bypass/yolo is not a good library default.
- The single unified parser trades clarity for performance; `py-agent-ctrl`
  should keep provider-specific parsers but share buffering and diagnostics.
- Skill auto-injection is workflow-specific and should not be in the bridge core.
- AGPL licensing on the parent repo means we should copy design ideas, not code.

## Gaps Relative To py-agent-ctrl

`py-agent-ctrl` already has provider-specific actions and normalized responses,
but it is weaker on process lifecycle, environment injection, stderr diagnostics,
stdin-mode robustness, worktree isolation, and structured multi-task execution.
