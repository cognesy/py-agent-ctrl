# Shared Streaming and Aggregate Pipeline Plan

bd epic: `bd-1jh.18` (`Make Streaming and Aggregate Execution Share One Pipeline`)

## Goal

Make `.execute()` and `.stream()` use the same provider parsing and reduction
path so aggregate and streaming behavior cannot drift.

The pipeline should preserve the current public API:

- `AgentCtrl.<provider>().execute(...) -> AgentResponse`
- `AgentCtrl.<provider>().stream(...) -> StreamResult`

Internally, both modes should share the same stages:

1. provider command construction;
2. subprocess launch;
3. JSONL parsing with diagnostics;
4. provider raw payload retention;
5. provider event mapping;
6. optional live event yield;
7. final provider response reduction.

## Non-goals

- Do not introduce async execution here.
- Do not implement ACP, JSON-RPC, or ACP transport behavior.
- Do not redesign tool-call lifecycle, cancellation, or error taxonomy.
- Do not change the public facade shape.
- Do not require live provider CLIs for the first implementation.

## Existing py-agent-ctrl Findings

The common parser contract from `bd-1jh.23` removed the largest source of
parser duplication:

- `services/core/parsing.py` owns `ProviderEventParser`,
  `ProviderResponseReducer`, `ProviderParseResult`, `parse_json_lines(...)`,
  and `stream_diagnostics_from(...)`.
- Every bridge now wraps its provider parser and reducer with
  `FunctionEventParser` and `FunctionResponseReducer`.
The shared pipeline work in `bd-1jh.18` then moved bridge execution mechanics
onto `ProviderExecutionPipeline`:

- aggregate paths call `ProviderExecutionPipeline.parse_output(...)`;
- stream paths call `ProviderExecutionPipeline.stream_command(...)`;
- the pipeline keeps `ProviderExecutionState` while streaming;
- Gemini provides a stream payload adapter for live tool-result pairing.

The remaining divergence is bridge-level execution structure:

- aggregate mode uses `run_command(...)`, captures full stdout/stderr, then
  parses after process exit;
- stream mode uses `stream_command_json_lines(...)`, yields events live, and
  does not build a final `AgentResponse`;
- stderr/timing diagnostics are richer for aggregate process output than stream
  output;
- Gemini still has stream-only `tool_use` / `tool_result` pairing in
  `GeminiBridge.stream(...)`.

## ACP SDK Reference Findings

Useful ACP SDK patterns, adapted without adopting ACP as a runtime contract:

- `Connection` separates raw frame receive, observers, dispatch, and task
  execution.
- `SessionAccumulator` consumes a stream of notifications and can produce a
  snapshot at any point.
- `ToolCallTracker` keeps lifecycle state outside raw frame parsing.
- `spawn_stdio_transport(...)` treats subprocess transport, stream reading, and
  shutdown as explicit infrastructure.

For `py-agent-ctrl`, the analogous design is an internal execution stream that
records parsed provider payloads and normalized events while optionally yielding
events live.

## Feasibility Experiment

I tested a small stream-style accumulator over the current provider fixtures.
For each raw line, it used `JsonLinesParser.parse_line(...)`, appended valid raw
payloads, emitted events through the provider `FunctionEventParser`, then
reduced the accumulated result through the provider `FunctionResponseReducer`.

The stream-style accumulator matched `parse_json_lines(...)` for:

- event type sequences;
- retained raw provider payloads;
- parse failure counts;
- final response fields, excluding random `execution_id`.

Fixtures tested:

- `claude_code/basic_stream.jsonl`
- `codex/basic_stream.jsonl`
- `codex/malformed_and_unknown.jsonl`
- `gemini/basic_stream.jsonl`
- `opencode/basic_stream.jsonl`
- `pi/basic_stream.jsonl`

Observed feasibility result:

- Claude: `3` events, `0` parse failures, text `pong`
- Codex normal: `7` events, `0` parse failures, text `Hello from codex`
- Codex malformed: `2` events, `2` parse failures, empty text
- Gemini: `5` events, `0` parse failures, text `Hello`
- OpenCode: `4` events, `0` parse failures, text `Hello OpenCode`
- Pi: `4` events, `0` parse failures, text `Hello world`

Conclusion: a shared execution pipeline is technically feasible as an
incremental layer on top of the parser contract. A rewrite of provider parsers
or reducers is not required first.

## Proposed Architecture

Add a shared internal module, likely
`libs/py_agent_ctrl/services/core/pipeline.py`, with:

```python
class ProviderPipeline:
    agent_type: AgentType
    event_parser: ProviderEventParser
    response_reducer: ProviderResponseReducer

    def parse_output(stdout: str, *, exit_code: int) -> AgentResponse: ...
    def stream_events(command: CommandSpec, ...) -> StreamResult: ...
```

More useful first-step primitives:

- `ProviderExecutionPipeline`: owns a parser and reducer pair.
- `ProviderExecutionState`: wraps `ProviderParseResult` while stream events are
  being accumulated.
- `parse_stdout(output: ProcessOutput) -> AgentResponse`: shared aggregate
  execution helper.
- `stream_command(command: CommandSpec) -> StreamResult`: shared stream helper
  that records state as it yields events.

The stream helper should expose accumulated state through diagnostics or a
private getter so tests can prove the same reducer can run after stream
exhaustion. It should not change `StreamResult` publicly unless a later task
decides that exposing final `AgentResponse` from streams is part of the public
contract.

## Provider-specific Escape Hatches

The pipeline must allow providers to customize live stream event emission while
still recording raw payloads and parser events.

Gemini needs this immediately:

- aggregate parsing sees `tool_use` and `tool_result` as raw payloads and pairs
  them inside `gemini_response_from_output(...)`;
- streaming currently suppresses separate unknown events and yields one
  `AgentToolCallEvent` after a matching `tool_result`.

The implementation supports an optional provider stream adapter:

```python
StreamPayloadAdapter = Callable[
    [dict[str, object], list[AgentEvent], ProviderExecutionState],
    Iterable[AgentEvent],
]
```

The pipeline always records the raw payload and parser events first. If no
adapter is provided, stream output yields those parsed events. If an adapter is
provided, it can suppress, replace, or combine live events without changing the
recorded state. Gemini uses this to suppress raw `tool_use` / `tool_result`
unknown events and emit one paired `AgentToolCallEvent`.

## Compatibility Constraints

- Keep `AgentBridge.execute(...)` and `AgentBridge.stream(...)` unchanged.
- Keep `StreamResult` iteration lazy.
- Keep `AgentResponse.raw_response` as provider raw payloads.
- Keep parse diagnostics bounded.
- Preserve Gemini stream tool pairing until the tool lifecycle epic changes it.
- Do not remove provider parser or reducer functions.

## Implementation Sequence

Status: implemented under `bd-1jh.18`.

1. Added shared pipeline primitives around the existing parser contract.
2. Added unit tests proving stream-style accumulation and aggregate parsing
   reduce to equivalent responses for all fixtures.
3. Migrated Codex and Claude.
4. Added adapter support and migrated OpenCode/Pi.
5. Migrated Gemini with a narrow adapter that preserves current stream tool
   pairing.
6. Documented the pipeline boundary in `docs/dev/architecture.md`.

## Risks

- Stream subprocess diagnostics still lack stderr tail and duration. Do not
  solve this inside the first pipeline task unless needed for correctness.
- `StreamResult` does not expose a final response. Adding that publicly would be
  useful but should be a separate compatibility decision.
- Gemini's live stream behavior differs from aggregate event emission; adapter
  support is required to avoid a behavior change.
- A pipeline class that also builds provider commands would mix responsibilities
  too early. Command builders should remain provider-owned.

## Open Questions

- Stream mode still does not expose `result.response` after exhaustion. That is
  a public API decision for a future task.
- Stream diagnostics do not include a reduced response. Current tests verify the
  same state can reduce to the aggregate response.
- The pipeline owns subprocess execution for streaming from `CommandSpec`, but
  provider command construction remains bridge-owned.
- Stream stderr/timing convergence should wait for the error taxonomy and
  cancellation epics.

## Task Breakdown

The implementation should be tracked under `bd-1jh.18` with these tasks:

1. Add shared pipeline state and fixture equivalence tests.
2. Migrate Codex and Claude to the shared pipeline.
3. Add provider stream adapter support and migrate OpenCode/Pi.
4. Migrate Gemini with preserved stream tool pairing.
5. Document the pipeline boundary and remove duplicate bridge code.

## Verification Plan

Use targeted checks per task plus:

- `uv run python -m pytest tests/unit/test_provider_fixtures.py`
- `uv run python -m pytest tests/unit/test_claude_bridge.py tests/unit/test_other_bridges.py`
- `uv run python -m pytest tests/unit/test_stream_result.py tests/unit/test_subprocess.py`
- `uv run python -m mypy libs/py_agent_ctrl apps`
- `uv run python -m ruff check libs/py_agent_ctrl tests/unit`
