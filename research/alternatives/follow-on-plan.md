# Follow-On Plan: Mature CLI Agent Abstraction Layer

Epic: `bd-bwl`

## Goal

Mature `py-agent-ctrl` into a robust in-process abstraction layer for CLI coding
agents. The library should preserve the simple facade:

```python
AgentCtrl.make("codex").in_directory(repo).execute(prompt)
```

while gaining the process hardening, provider-native option surfaces,
observability, session semantics, and event richness surfaced by the alternatives
review.

## Inputs

This plan is based on:

- `research/alternatives/README.md`
- `research/alternatives/myclaude-codeagent-wrapper.md`
- `research/alternatives/hapi.md`
- `research/alternatives/agent-client-protocol.md`
- `research/alternatives/claude-agent-sdk-python.md`
- `research/alternatives/missed-problems.md`
- `docs/dev/architecture.md`
- Current `py-agent-ctrl` modules under `libs/py_agent_ctrl/`

## Constraints

- Keep `py-agent-ctrl` an in-process Python library over subprocess CLIs.
- Do not adopt an HTTP server control surface.
- Preserve provider-specific option surfaces. Do not force every provider into
  one lowest-common-denominator config.
- Keep Pydantic as the schema layer for public request/response/event models.
- Keep CLI apps thin; process and provider logic belongs under `libs/`.
- Use `uv` for verification.
- Respect current worktree state; do not revert unrelated in-progress edits.

## Approach

Build in layers:

1. Establish shared execution primitives.
2. Migrate providers onto the shared executor.
3. Improve parsing and diagnostics.
4. Add richer events and provider-specific option models.
5. Add permission/session abstractions where the provider data supports them.
6. Add optional isolation/orchestration features above the core bridge layer.

This avoids turning `py-agent-ctrl` into a daemon or workflow engine while still
absorbing the high-value lessons from the cloned projects.

## Proposed Task Breakdown

### 1. Shared Command Executor

Create a shared `CommandSpec`, `ProcessOutput`, and `CommandExecutor` under
`libs/py_agent_ctrl/services/core/`.

Purpose:

- Replace direct `subprocess.run`/`Popen` duplication.
- Centralize timeout, cancellation, cwd/env handling, stderr tail capture,
  graceful shutdown, and parse-diagnostic plumbing.
- Provide the foundation for `SandboxDriver`.

Notes:

- Fold existing `bd-aga` into this work or make it a child/dependency.
- Borrow design ideas from `myclaude/codeagent-wrapper` and ACP Python SDK
  transport, not code.

### 2. JSONL Buffering and Parse Diagnostics

Add shared JSONL parsing helpers that support:

- line buffering for chunked stream data
- max line / max buffer limits
- skipped non-JSON line accounting
- parse failure samples
- raw event retention
- preservation of parsed output on non-zero process exit

Purpose:

- Keep provider-specific parsers, but make buffering and diagnostics consistent.
- Prevent long/partial JSON output from corrupting streams.

### 3. Migrate Provider Bridges To Shared Executor

Move Claude Code, Codex, OpenCode, Pi, and Gemini bridges from direct subprocess
calls to the shared executor.

Expected outcomes:

- Each bridge builds a command/env spec and delegates execution/streaming.
- Behavior stays backward compatible for existing tests.
- Provider-specific argv builders remain provider-specific.

### 4. Provider Environment and Binary Preflight

Add explicit provider env builders and stronger preflight:

- per-provider env injection hooks
- API-key/token masking in diagnostics
- provider-specific env cleanup such as avoiding nested Claude env issues
- optional version preflight where provider behavior depends on CLI version

Purpose:

- Avoid hidden inherited-env bugs and make failures more actionable.

### 5. Sandbox and Worktree Isolation

Turn `SandboxDriver` into a real execution policy:

- `host` first
- driver abstraction for future docker/podman/firejail/bubblewrap
- policy fields for cwd, writable roots, extra readable roots, env inheritance,
  network, temp dirs, timeout
- optional git worktree isolation as a separate high-value mode

Purpose:

- Make sandbox configuration real without blocking host-mode users.

Priority note:

- User clarified on 2026-04-11 that sandbox/worktree isolation is super low
  priority for now. Keep this task off the critical path. Do not let it block
  executor, parsing, bridge migration, events, observability, provider options,
  or sessions.

### 6. Richer Event Model

Extend normalized events while preserving current event classes:

- reasoning/thought events
- plan update events
- tool call start/update/result events
- usage/token update events
- rate limit/provider warning events
- file diff/change events where providers expose them
- unknown/raw event preservation

Purpose:

- Match what HAPI, ACP, and provider SDKs demonstrate without breaking existing
  `AgentTextEvent`, `AgentToolCallEvent`, and `AgentResultEvent` users.

### 7. Streaming Wiretap Semantics

Harden streaming callbacks:

- deduplicate cumulative text streams
- suppress known internal provider JSON
- reject or ignore stale events when session/turn IDs are available
- wait for a short quiet period when a provider returns before all updates drain

Purpose:

- Avoid duplicated text, leaked control JSON, and late event loss.

### 8. Permission Abstraction

Add an optional permission request model and broker:

- permission request ID
- tool call ID
- option ID/kind/name
- pending request state
- approve once / approve for session / reject / abort / cancel outcomes
- callback hooks for user policy

Purpose:

- Prepare for providers that expose permission requests through hooks/ACP/native
  event streams without forcing every provider to support it.

### 9. Session Management APIs

Add normalized session operations where supported:

- list sessions
- read session metadata
- resume/continue already exist but should be modeled consistently
- optional fork/tag/rename/delete only for providers with safe transcript APIs
- provider session ID vs execution ID documentation/tests

Purpose:

- Make session continuity a first-class abstraction, not just a command flag.

### 10. Provider-Native Option Models

Add typed provider options or dataclass/Pydantic models behind fluent methods:

- Claude Code: tools, allowed/disallowed tools, permission mode, settings,
  add dirs, MCP config, hooks where appropriate
- Codex: sandbox/approval, reasoning effort, config overrides, images
- Gemini: approval mode, sandbox, extensions, MCP servers, policies
- OpenCode/Pi: keep target-native controls explicit

Purpose:

- Reduce unchecked `provider_options: dict[str, Any]` use over time while
  preserving escape hatches.

### 11. Observability and Error Taxonomy

Add better normalized diagnostics:

- binary not found
- working directory missing
- timeout
- cancellation
- process failure with stderr tail
- JSON decode failure
- provider parse failure
- execution ID, provider session ID, backend, cwd, argv preview, PID, durations

Purpose:

- Make bridge failures actionable for xqa and other callers.

### 12. Optional ACP Projection Adapter

Add a research/experimental adapter that projects `py-agent-ctrl` normalized
events to ACP-like session updates.

Purpose:

- Keep an interoperability path open without making ACP the core runtime.

## Dependencies

Recommended dependency order:

1. Shared Command Executor
2. JSONL Buffering and Parse Diagnostics
3. Provider Bridge Migration
4. Provider Environment and Binary Preflight
5. Richer Event Model
6. Streaming Wiretap Semantics
7. Permission Abstraction
8. Session Management APIs
9. Provider-Native Option Models
10. Observability and Error Taxonomy
11. Optional ACP Projection Adapter
12. Sandbox and Worktree Isolation (low priority / backlog)

Some tasks can overlap after the executor/parser foundation is done:

- Provider-native option models can proceed in parallel with richer event
  modeling once bridge migration is complete.
- Permission and session APIs can be split by provider support.
- ACP projection should wait until the richer event model has stabilized.
- Sandbox/worktree isolation should wait behind executor/env foundations but
  should not block the main maturity work.

## Risks

- Overgeneralizing provider options could weaken target-native support.
- Adding sandbox support without a clear execution policy could create false
  security confidence.
- Richer events may break downstream users if existing event classes change
  instead of extending the model.
- Session management is provider-specific and may require transcript scanning
  that is fragile across CLI versions.
- Permission APIs can block or deadlock if cancellation does not resolve pending
  requests.

## Open Questions

- Should `bd-aga` be reparented under `bd-bwl`, or should we keep it as a
  discovered follow-up outside the epic?
- Which provider should be the first migration target for the shared executor:
  Claude Code, Codex, or the smallest bridge?
- Do we want worktree isolation in `py-agent-ctrl` core, or in a separate
  orchestration helper?
- Should ACP projection be part of the main package or remain in
  `research/experimental` until a real caller needs it?

## Review Request

Before creating bd child tasks, review:

- whether the task list is too broad or missing high-value items
- whether `Sandbox and Worktree Isolation` should remain low priority
- whether `Permission Abstraction` should be included now or deferred
- whether ACP projection should be planned at all
