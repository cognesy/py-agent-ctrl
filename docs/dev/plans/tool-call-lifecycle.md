# Tool Call Lifecycle Plan

bd epic: `bd-1jh.11` (`Introduce a First-class Tool Call Lifecycle`)

## Goal

Represent tool calls as lifecycle-aware events while preserving the existing
final `AgentResponse.tool_calls` snapshot list.

The first implementation should let callers distinguish:

- a tool call that has started or is pending;
- a tool call that is in progress;
- a tool call that completed successfully;
- a tool call that failed or was cancelled;
- a provider that only exposes a final snapshot.

## Non-goals

- Do not remove the current `ToolCall` model.
- Do not remove or rename `AgentToolCallEvent.type == "tool_call"`.
- Do not make provider CLIs ACP-native.
- Do not redesign terminal/command events here.
- Do not change permission, cancellation, or trace persistence behavior here.

## Current py-agent-ctrl Findings

Current public models:

- `ToolCall` is the compatibility snapshot with `id`, `name`, `kind`,
  `arguments`, `output`, `is_error`, `status`, and `raw`.
- `AgentToolCallEvent` wraps one `ToolCall` and has no lifecycle phase.
- `AgentResponse.tool_calls` is built by appending `AgentToolCallEvent.tool_call`
  snapshots.
- `BaseAgentAction.on_tool_call(...)` receives only the `ToolCall` snapshot.

Current provider behavior:

- Claude Code emits a `tool_use` as a pending `AgentToolCallEvent`, but
  `tool_result` is currently normalized as `AgentUnknownEvent`.
- Codex emits completed snapshots for `command_execution`, `mcp_tool_call`,
  `file_change`, `web_search`, `reasoning`, and `plan_update` items.
- Gemini aggregate parsing stores `tool_use` and `tool_result` as
  `AgentUnknownEvent` records and pairs them in the response reducer. Live
  streaming pairs them in the bridge adapter and emits one `AgentToolCallEvent`.
- OpenCode emits a `tool_use` snapshot whose provider state may already be
  completed or failed.
- Pi emits a `tool_execution_end` snapshot only.

## ACP SDK Reference Findings

Useful patterns from `acp-python-sdk`:

- `src/acp/contrib/tool_calls.py` keeps mutable tool state in a tracker keyed by
  provider/external IDs.
- `ToolCallTracker.start(...)` and `progress(...)` separate lifecycle updates
  from the final view.
- `TrackedToolCallView` is immutable and can be used to expose current state
  without leaking tracker internals.
- `SessionAccumulator` merges a stream of tool-call notifications into a stable
  snapshot.

Adaptation for `py-agent-ctrl`:

- Add lifecycle state to the existing event stream instead of adopting ACP
  schema objects.
- Keep final `ToolCall` snapshots as the public compatibility surface.
- Add an internal tracker/reducer that can merge lifecycle events into final
  snapshots.

## Feasibility Experiment

I replayed current provider fixtures through a tiny tracker that inferred
`started` versus `completed` from existing `ToolCall.status` values.

Observed:

- Claude fixture: one pending `Read` event, inferable as `started`.
- Codex fixture: two final snapshots, inferable as `completed`/`failed`.
- Gemini fixture: no `AgentToolCallEvent` in aggregate parsing, but two raw
  unknown tool references (`pending_tool`, `tool_result`) that can be mapped.
- OpenCode fixture: one completed `bash` snapshot.
- Pi fixture: one completed `bash` snapshot.

Conclusion: lifecycle support is feasible incrementally. The safe first slice
is model/tracker compatibility plus provider-by-provider parser migration.

## Proposed Model/API Changes

Add a lifecycle enum:

```python
class ToolCallPhase(StrEnum):
    STARTED = "started"
    UPDATED = "updated"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SNAPSHOT = "snapshot"
```

Compatibility options:

- Add `phase: ToolCallPhase | None = None` to `ToolCall`.
- Add `phase: ToolCallPhase | None = None` to `AgentToolCallEvent`.
- Keep `ToolCall.status` unchanged.
- Keep `AgentResponse.tool_calls` as final/snapshot `ToolCall` objects.
- Keep `on_tool_call` callback signature unchanged.

Internal helper:

- Add `services/core/tool_calls.py` with a `ToolCallLifecycleTracker`.
- The tracker should merge events by stable `ToolCall.id` when present.
- Missing IDs can fall back to a deterministic local key per stream/reduction.
- The tracker should expose final snapshots for `AgentResponse.tool_calls`.

## Provider Migration Strategy

1. Add model fields and tracker with compatibility tests; do not change parser
   output yet.
2. Migrate Claude Code first because it clearly exposes a start/pending event.
3. Migrate Gemini aggregate and live stream behavior because it has explicit
   start/result raw records but currently hides them differently in aggregate
   versus stream mode.
4. Migrate Codex, OpenCode, and Pi by marking their current snapshots as
   `SNAPSHOT`, `COMPLETED`, `FAILED`, or `CANCELLED` based on status.
5. Update reducers to use the tracker for final `AgentResponse.tool_calls`
   while keeping final list behavior compatible.
6. Update docs and callbacks tests.

## Compatibility Constraints

- Existing tests that assert event type `tool_call` should continue to pass.
- Existing users reading `event.tool_call.status` and `response.tool_calls`
  should continue to work.
- New lifecycle fields must be additive.
- Do not force providers without start events to pretend they have true starts.
  Use `SNAPSHOT` or inferred completion where that is more honest.

## Risks

- Provider payloads do not all expose start/update/completion separately.
- Gemini currently has different aggregate and live stream behavior; migration
  must preserve current response snapshots and stream pairing.
- A lifecycle tracker can accidentally duplicate final `tool_calls` if reducers
  append both lifecycle starts and completions without merging.
- Public callback semantics could become noisy if every update calls
  `on_tool_call`; keep callback compatibility first.

## Open Questions

- Should `SNAPSHOT` be a real phase, or should `phase=None` mean snapshot-only?
- Should `on_tool_call` fire for every lifecycle update or only final snapshots?
- Should lifecycle events later become separate event types
  (`tool_call_started`, `tool_call_updated`) instead of one `phase` field?
- How should missing provider tool IDs be generated for durable traces?

## Task Breakdown

The implementation should be tracked under `bd-1jh.11` with these tasks:

1. Add lifecycle model fields and tracker primitives.
2. Migrate Claude Code lifecycle emission and reducer behavior.
3. Migrate Gemini lifecycle emission while preserving stream pairing.
4. Migrate Codex, OpenCode, and Pi snapshot phase mapping.
5. Update callbacks, event docs, and lifecycle fixture assertions.

## Verification Plan

- `uv run python -m pytest tests/unit/test_provider_fixtures.py`
- `uv run python -m pytest tests/unit/test_claude_bridge.py tests/unit/test_other_bridges.py`
- `uv run python -m pytest tests/unit/test_action_callbacks.py`
- `uv run python -m mypy libs/py_agent_ctrl apps`
- `uv run python -m ruff check libs/py_agent_ctrl tests/unit`
