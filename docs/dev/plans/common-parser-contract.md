# Common Parser Contract Plan

bd epic: `bd-1jh.23` (`Replace Provider-specific Stream Parsers With a Common Parser Contract`)

## Goal

Introduce a common parser contract for provider-native JSONL records so
`py-agent-ctrl` can parse Claude Code, Codex, Gemini, OpenCode, and Pi streams
through one shared execution path while keeping provider-specific event mapping
inside each provider package.

The contract should cover:

- raw provider payload ingestion;
- normalized `AgentEvent` emission;
- parse diagnostics;
- raw-event retention for debugging;
- aggregate response reduction;
- compatibility with the current sync `.execute()` and `.stream()` APIs.

## Non-goals

- Do not implement ACP or reuse ACP schema models as the runtime model.
- Do not redesign the event taxonomy in this task; lifecycle/content/error
  redesigns have separate epics.
- Do not replace provider command builders.
- Do not change public `AgentCtrl.<provider>().execute(...)` or `.stream(...)`
  behavior.
- Do not require live provider CLIs to verify the first migration.

## Existing py-agent-ctrl Findings

Current provider parsers already have a near-common shape:

- `parse_claude_events(raw: dict[str, Any]) -> list[AgentEvent]`
- `parse_codex_events(raw: dict[str, Any]) -> list[AgentEvent]`
- `parse_gemini_events(raw: dict[str, Any]) -> list[AgentEvent]`
- `parse_opencode_events(raw: dict[str, Any]) -> list[AgentEvent]`
- `parse_pi_events(raw: dict[str, Any]) -> list[AgentEvent]`

Provider response reducers are still provider-specific:

- `events_to_response(...)`
- `codex_response_from_output(...)`
- `gemini_response_from_output(...)`
- `opencode_response_from_output(...)`
- `pi_response_from_output(...)`

The bridges duplicate the same pattern:

1. Build a provider command.
2. Run or stream JSONL.
3. Keep raw events.
4. Convert raw payloads to `AgentEvent`.
5. Build `AgentResponse` in aggregate mode or yield events in stream mode.
6. Copy parse diagnostics into either response fields or `StreamDiagnostics`.

Existing shared primitives:

- `JsonLinesParser`
- `JsonParseDiagnostics`
- `StreamDiagnostics`
- `AgentEvent`
- `AgentResponse`
- provider-specific response reducers

## ACP SDK Reference Findings

Useful ACP SDK patterns:

- `src/acp/helpers.py` keeps schema-aligned construction helpers separate from
  transport code.
- `src/acp/connection.py` separates raw JSON frame handling, observer capture,
  dispatch, and handler execution.
- `src/acp/contrib/session_state.py` accumulates a stream of typed updates into
  a snapshot instead of mixing stream parsing with final-state reduction.
- `tests/test_golden.py` keeps helper output aligned to golden serialized
  payloads.

Adaptation for `py-agent-ctrl`:

- Use typed internal parser/reducer helpers, not ACP protocol classes.
- Keep raw frame parsing separate from provider event mapping.
- Keep provider-specific reducers behind a common call shape.
- Add fixture tests as the equivalent of ACP golden tests.

## Feasibility Experiment

I ran a small local experiment over existing fixtures using a wrapper shaped as:

```python
class FunctionParser:
    agent_type: AgentType
    def parse_payload(self, payload: dict[str, object]) -> list[AgentEvent]: ...
```

The wrapper fed `JsonLinesParser` output into the existing Claude and Codex
parser functions, then used the existing provider reducers.

Observed results:

- `tests/fixtures/claude_code/basic_stream.jsonl`
  - events: `text`, `tool_call`, `result`
  - response text: `pong`
  - tool: `Read`, kind `read`, status `pending`
  - parse failures: `0`
- `tests/fixtures/codex/basic_stream.jsonl`
  - events: `result`, `text`, `tool_call`, `tool_call`, `result`, `usage`,
    `unknown`
  - response text: `Hello from codex`
  - tools: `bash` failed execute, `web_search` completed search
  - parse failures: `0`
- `tests/fixtures/codex/malformed_and_unknown.jsonl`
  - events: `result`, `unknown`
  - parse failures: `2`
  - samples: `not-json`, `["not","an","object"]`

Conclusion: a common contract is technically feasible as an incremental wrapper
around existing parser/reducer functions. A full parser rewrite is unnecessary
for the first implementation.

## Proposed Architecture

Add a new shared module, likely `libs/py_agent_ctrl/services/core/parsing.py`,
with small internal types:

```python
class ProviderEventParser(Protocol):
    agent_type: AgentType
    def parse_payload(self, payload: dict[str, object]) -> list[AgentEvent]: ...

class ProviderResponseReducer(Protocol):
    agent_type: AgentType
    def reduce(
        self,
        *,
        events: list[AgentEvent],
        raw_events: list[dict[str, object]],
        exit_code: int,
        parse_failures: int,
        parse_failure_samples: list[str],
    ) -> AgentResponse: ...
```

Concrete helpers:

- `FunctionEventParser`: wraps existing `parse_*_events` functions.
- `FunctionResponseReducer`: wraps existing provider response functions.
- `ProviderParseResult`: captures `agent_type`, `events`, `raw_events`, and
  `JsonParseDiagnostics`.
- `parse_json_lines(stdout, parser) -> ProviderParseResult`.
- `iter_parsed_json_lines(lines, parser, diagnostics) -> Iterator[AgentEvent]`
  or an equivalent streaming helper.
- `stream_diagnostics_from(...) -> StreamDiagnostics`.

Provider bridge migration should start with Codex because current fixtures cover
both normal and malformed payloads. Claude Code should be second because its
fixture covers text/tool/result. Gemini, OpenCode, and Pi can follow after the
contract is proven.

## Compatibility Constraints

- `AgentResponse.raw_response` remains a list of provider raw payloads.
- Existing parser functions stay importable for now.
- Existing response reducer functions stay importable for now.
- Stream iteration remains lazy.
- `StreamResult.diagnostics` still works after exhaustion.
- Provider bridge `capabilities()` output does not change.

## Implementation Sequence

Status: implemented under `bd-1jh.23`.

1. Added the shared parser contract module and tests against Claude/Codex
   fixtures, without changing bridges.
2. Migrated Codex bridge execute/stream to the shared parsing helpers.
3. Migrated Claude Code bridge execute/stream.
4. Added minimal Gemini/OpenCode/Pi fixtures.
5. Migrated Gemini/OpenCode/Pi bridge execute/stream paths where behavior could
   be preserved.
6. Documented parser contract ownership in `docs/dev/architecture.md`.

## Risks

- Gemini aggregate parsing currently pairs `tool_use` and `tool_result` during
  response reduction, while stream mode pairs them inside the bridge. The common
  contract should preserve that behavior first and defer lifecycle redesign to
  `bd-1jh.11`.
- A generic reducer is premature; provider reducers still encode provider usage,
  cost, session, and final-text details.
- Stream stderr and timeout diagnostics are still limited by the subprocess
  streaming implementation. Do not solve that here.
- Adding fixtures for Gemini/OpenCode/Pi may require synthetic minimal payloads
  if real provider payloads are not available.

## Open Questions

- `ProviderParseResult` currently stores only bounded invalid-line samples
  through `JsonParseDiagnostics`. Persisting every invalid raw line should be a
  separate trace-format decision.
- Parser exceptions are not yet normalized. Deciding whether they become
  warning events, diagnostics, or hard failures belongs with the future error
  taxonomy work.
- Provider parser objects currently use `FunctionEventParser` wrappers in each
  bridge. Dedicated provider parser classes can wait until a provider needs
  parser-local state.

## Task Breakdown

The implementation should be tracked under `bd-1jh.23` with these tasks:

1. Add shared parser contract primitives.
2. Migrate Codex bridge to the shared parser contract.
3. Migrate Claude Code bridge to the shared parser contract.
4. Add minimal Gemini/OpenCode/Pi parser fixtures.
5. Migrate Gemini/OpenCode/Pi bridges.
6. Document the internal parser contract and retire duplicate bridge code.

## Verification Plan

Use targeted checks per task plus the shared gates:

- `uv run python -m pytest tests/unit/test_provider_fixtures.py`
- `uv run python -m pytest tests/unit/test_claude_bridge.py tests/unit/test_other_bridges.py`
- `uv run python -m pytest tests/unit/test_stream_result.py tests/unit/test_subprocess.py`
- `uv run python -m mypy libs/py_agent_ctrl apps`
- `uv run python -m ruff check libs/py_agent_ctrl tests/unit`
