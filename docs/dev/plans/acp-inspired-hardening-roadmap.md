# ACP-inspired Hardening Roadmap

bd parent: `bd-1jh` (`ACP lessons for py-agent-ctrl hardening`)

## Goal

Use ACP and `acp-python-sdk` as design references to harden `py-agent-ctrl`
without turning it into an ACP runtime.

The target state is a stronger Python API for executing existing CLI coding
agents:

- normalized streaming and aggregate execution share durable contracts;
- provider parsers emit richer typed events with diagnostics;
- sessions, permissions, cancellation, errors, traces, and output rendering are
  explicit instead of ad hoc;
- the public facade stays focused on installed provider CLIs: Claude Code,
  Codex, Gemini, OpenCode, and Pi.

## Non-goals

- Do not reintroduce an ACP adapter.
- Do not expose `py-agent-ctrl` as an ACP agent, ACP client, JSON-RPC server, or
  tool server.
- Do not replace provider CLIs with vendor SDKs.
- Do not break the current `AgentCtrl.<provider>().execute(...)` and
  `.stream(...)` shape without a migration plan.
- Do not implement the epics directly from their original one-paragraph
  descriptions. Each implementation area needs accepted tasks first.

## Research Baseline

### py-agent-ctrl

The live codebase is currently split into:

- `api`: Pydantic request/response/event/capability/session/permission models,
  `AgentCtrl`, and the `AgentBridge` protocol.
- `actions`: fluent provider facade classes, execute/stream wrappers, callback
  dispatch, session helpers, and the current in-memory `PermissionBroker`.
- `services/core`: binary lookup, environment building, subprocess execution,
  JSONL parsing, error classes, and path normalization.
- `services/bridges`: provider-specific command builders, bridges, and parsers.
- `cli.py`: thin `ctrlagent` command implementation with plain text output.
- `tests/unit`: focused tests for command builders, parsers, facade behavior,
  callbacks, permissions, subprocess handling, stream results, and golden
  provider fixtures.

The low-hanging ACP lessons already changed the baseline by removing the fake
ACP adapter, adding stable event docs, normalizing tool status/kind values,
expanding bridge capabilities, adding provider JSONL fixtures, surfacing stream
diagnostics, and normalizing paths before command building.

### ACP Python SDK

The SDK is not a runtime dependency target, but it provides useful patterns:

- `src/acp/interfaces.py` separates `Agent` and `Client` responsibilities and
  makes session lifecycle, prompt, cancellation, file, terminal, and permission
  operations explicit.
- `src/acp/helpers.py` provides small typed constructors such as text/content
  blocks, plan entries, tool call starts/updates, diff content, and terminal
  references.
- `src/acp/contrib/tool_calls.py` keeps tool-call lifecycle state outside raw
  event parsing through `ToolCallTracker`.
- `src/acp/contrib/permissions.py` models permission requests as structured
  choices tied to tool calls.
- `src/acp/contrib/session_state.py` accumulates notifications into a session
  snapshot with merged tool state, plan state, mode, commands, messages, and
  thoughts.
- `src/acp/connection.py`, `src/acp/task/*`, `src/acp/stdio.py`, and
  `src/acp/transports.py` demonstrate async JSON-RPC framing, task supervision,
  receive/send state, stream observers, bounded stdio, default environment
  handling, and graceful subprocess shutdown.
- `tests/test_golden.py` and `tests/golden/*` demonstrate schema/golden
  discipline for generated helpers and serialized protocol payloads.

## Compatibility Constraints

- Existing Pydantic model names remain importable where possible.
- Existing fluent provider actions remain the primary public API.
- Provider command builders should stay provider-native and should not learn ACP
  concepts.
- Streaming remains synchronous until the async execution epic is accepted and
  implemented.
- Any new internal model must preserve provider raw payloads for diagnostics.
- New trace/replay features must redact or opt-in to potentially sensitive raw
  content.

## Migration Strategy

1. Add new internal contracts behind existing public facades.
2. Keep old fields until replacements are documented and tested.
3. Migrate one provider at a time when parser or event contracts change.
4. Use recorded fixtures and replay tests before changing live-provider code.
5. Document capability changes before enforcing builder validation.
6. Treat async, state-machine, policy, trace, and renderer work as additive
   until a release plan says otherwise.

## Cross-cutting Verification

Every implementation task should choose a smaller targeted gate plus the common
module gates when it touches shared code:

- `uv run python -m pytest tests/unit`
- `uv run python -m mypy libs/py_agent_ctrl apps`
- `uv run python -m ruff check libs/py_agent_ctrl tests`
- provider-specific fixture tests under `tests/unit/test_provider_fixtures.py`
- docs inspection for changed user-facing contracts

## Epic Plans

### bd-1jh.11: First-class Tool Call Lifecycle

Goal: split one-shot `ToolCall` snapshots into start/progress/completion events
without losing the existing final `AgentResponse.tool_calls` list.

Affected modules: `api/events.py`, `api/models.py`, provider parsers, bridge
reducers, `actions/base.py`, fixture tests, event docs.

Proposed model/API changes:

- Add lifecycle event variants or a versioned `AgentToolCallEvent.phase` field.
- Keep current `ToolCall` as the snapshot type for compatibility.
- Add a reducer that can merge lifecycle events into final snapshots.

Task breakdown:

- Design the lifecycle contract and compatibility reducer.
- Implement provider parser migration for one provider, then the rest.
- Add fixture, reducer, docs, and callback tests.

Risks/open questions: provider streams do not all expose starts and completions
cleanly; decide whether inferred phases are acceptable.

### bd-1jh.12: Structured Content Model

Goal: support text, images, resource links, embedded resources, tool content,
diffs, and terminal references as typed content blocks where providers expose
them.

Affected modules: `api/models.py`, `api/events.py`, provider parsers, command
builders for image/file options, docs, fixtures.

Proposed model/API changes:

- Introduce a `ContentBlock` union inspired by ACP helpers.
- Keep `AgentTextEvent.text` and `AgentResponse.text` as convenience views.
- Add conversion helpers from content blocks to plain text.

Task breakdown:

- Design content models and plain-text compatibility behavior.
- Implement content extraction in events/responses.
- Add golden tests and user docs for rich content.

Risks/open questions: binary content should likely remain references or base64
only when provider-native payloads already contain it.

### bd-1jh.13: Execution Policy Layer

Goal: replace the current pending-request store with a policy layer that can
decide allow/reject/prompt behavior by provider, tool kind, cwd, path scope, and
provider-native permission mode.

Affected modules: `actions/permissions.py`, provider actions, command builders,
capabilities, path handling, docs, tests.

Proposed model/API changes:

- Add a `ExecutionPolicy` or `AgentPolicy` model.
- Keep provider-native flags as low-level escape hatches.
- Add structured policy evaluation results and optional callbacks.

Task breakdown:

- Research provider permission flags and define policy schema.
- Implement local policy validation before launch.
- Wire provider-native permission modes and docs/tests.

Risks/open questions: not all providers expose permission callbacks; policy may
start as preflight plus command flag mapping only.

### bd-1jh.14: Cooperative Cancellation

Goal: give callers a real cancellation handle for long-running streams instead
of relying only on process timeout or process death.

Affected modules: `StreamResult`, `services/core/subprocess.py`, bridge stream
methods, actions/callbacks, tests.

Proposed model/API changes:

- Add an execution handle with `cancel()` and final diagnostics.
- Keep `for event in result` compatible.
- Distinguish cooperative provider cancellation from forced process kill.

Task breakdown:

- Design cancellation handle and subprocess lifecycle.
- Implement sync cancellation for streaming subprocesses.
- Add timeout/cancel tests and docs.

Risks/open questions: provider-native semantic cancellation may be unavailable,
so first pass may be process-level cancellation with clear diagnostics.

### bd-1jh.15: Execution Identity Versus Provider Session Identity

Goal: make local execution IDs, provider session IDs, and future trace IDs
unambiguous across requests, streams, and stored sessions.

Affected modules: `api/models.py`, `api/events.py`, `api/ids.py` if introduced,
bridges, reducers, docs.

Proposed model/API changes:

- Add explicit `execution_id`, `provider_session_id`, and optional `trace_id`
  terminology.
- Preserve `session_id` as an alias or compatibility field until migration.

Task breakdown:

- Design identity model and migration policy.
- Implement IDs consistently in execute and stream paths.
- Update docs/tests and deprecation notes.

Risks/open questions: public `session_id` is already exposed; renaming must be
incremental.

### bd-1jh.16: Terminal/Command Event Model

Goal: represent command execution as structured data instead of generic tool
text when providers expose terminal-like operations.

Affected modules: `api/events.py`, `api/models.py`, provider parsers, fixtures,
docs.

Proposed model/API changes:

- Add `AgentCommandEvent` or command content variant with command, args, cwd,
  exit code, stdout/stderr tail, and status.
- Map existing tool kind `execute` into command-aware events where possible.

Task breakdown:

- Design command event schema and relation to `ToolCall`.
- Implement provider parser mapping for command-like events.
- Add fixtures and rendering/docs tests.

Risks/open questions: provider output may include partial command text without
stable structured fields.

### bd-1jh.17: File Change / Diff Events

Goal: expose file edits as first-class events with path/action/diff/content
instead of burying edits inside raw provider payloads.

Affected modules: `api/events.py`, `api/models.py`, provider parsers, fixtures,
docs.

Proposed model/API changes:

- Expand `AgentFileChangeEvent` into typed action/content variants.
- Add diff content compatible with future structured content blocks.

Task breakdown:

- Design file-change event schema and redaction rules.
- Implement mappings for providers with file edit payloads.
- Add fixtures and docs for edit inspection workflows.

Risks/open questions: raw diffs can be large or sensitive; traces should make
redaction policy explicit.

### bd-1jh.18: Shared Streaming/Aggregate Pipeline

Goal: make `.execute()` and `.stream()` consume the same parser/reducer path so
they cannot drift.

Affected modules: bridges, parsers, reducers, subprocess JSONL parsing,
`AgentResponse` construction, tests.

Proposed model/API changes:

- Introduce provider parser objects that emit normalized events.
- Add one reducer from event stream to final `AgentResponse`.
- Keep existing public methods unchanged.

Task breakdown:

- Design parser/reducer interfaces.
- Migrate one provider as a proof of concept.
- Migrate remaining providers and remove duplicate reduction.

Risks/open questions: aggregate execution currently has access to full stdout
and stderr while streaming has partial line state; diagnostics must converge.

### bd-1jh.19: Error Taxonomy

Goal: replace mixed exceptions, exit codes, and parse counters with structured
error categories that Python callers can handle without string parsing.

Affected modules: `services/core/errors.py`, subprocess output, stream
diagnostics, bridges, facade docs, tests.

Proposed model/API changes:

- Add error code/category fields and structured diagnostic objects.
- Preserve current exception classes as compatibility subclasses or wrappers.

Task breakdown:

- Design error categories and mapping matrix.
- Implement core subprocess and binary/path errors.
- Extend provider parse and response diagnostics.

Risks/open questions: decide which failures raise exceptions and which return
`AgentResponse` diagnostics.

### bd-1jh.20: Capability-driven Builder Validation

Goal: validate unsupported options before launching provider CLIs.

Affected modules: `BridgeCapabilities`, provider actions, command builders,
facade/action helpers, docs, tests.

Proposed model/API changes:

- Extend capabilities with option schemas and supported modes.
- Add preflight validation for fluent provider options.
- Keep provider-native option escape hatches explicit.

Task breakdown:

- Design option schema and validation errors.
- Implement validation in action/bridge preflight.
- Add provider-specific tests and docs.

Risks/open questions: command-line provider capabilities can change by installed
CLI version; static validation should not overpromise.

### bd-1jh.21: Internal Agent Turn State Machine

Goal: model an execution as a turn lifecycle with states for preparing,
running, streaming, awaiting permission, cancelling, completed, and failed.

Affected modules: actions, services/core execution, stream result, permission
and cancellation future work, tests.

Proposed model/API changes:

- Add internal state objects; do not expose them as the primary user API yet.
- Emit diagnostics from state transitions.

Task breakdown:

- Design state machine and transition invariants.
- Implement internally for streaming execution.
- Extend to aggregate execution and permission/cancel paths.

Risks/open questions: a large refactor should follow shared parser/reducer work
to avoid duplicating state logic.

### bd-1jh.22: Async-native Execution

Goal: add async subprocess and async stream APIs for web apps, notebooks, and
orchestrators while preserving sync APIs.

Affected modules: services/core subprocess, actions, facade, bridges, tests,
docs.

Proposed model/API changes:

- Add `async_execute` and `async_stream` or separate async action facades.
- Reuse sync models and parser contracts.
- Avoid making sync APIs wrappers around unsafe event-loop calls.

Task breakdown:

- Design async API surface and subprocess abstraction.
- Implement async core execution and one provider.
- Complete provider migration and docs/tests.

Risks/open questions: sync/async duplication should wait for the common parser
contract.

### bd-1jh.23: Common Parser Contract

Goal: replace provider-specific parser conventions with a common protocol that
consumes raw records and emits normalized events plus diagnostics.

Affected modules: provider parsers, bridges, `services/core/subprocess.py`,
fixture tests.

Proposed model/API changes:

- Add a `ProviderParser` protocol and `ParseResult`/diagnostics model.
- Keep provider-specific payload parsing in provider packages.

Task breakdown:

- Design parser protocol and diagnostics contract.
- Migrate Codex and Claude as the first two parsers.
- Migrate Gemini/OpenCode/Pi and update fixtures.

Risks/open questions: providers differ in whether tool completions require
stateful pairing.

### bd-1jh.24: Session Store

Goal: track provider sessions locally so list/load/resume/continue workflows can
be reliable across providers.

Affected modules: `actions/sessions.py`, `api/models.py`, bridges, CLI, docs,
storage tests.

Proposed model/API changes:

- Add a simple file-backed session store with provider, cwd, session ID,
  execution ID, timestamps, title, and raw metadata.
- Keep provider-native resume/continue flags.

Task breakdown:

- Design storage schema and location policy.
- Implement store and facade/session APIs.
- Add CLI commands, docs, and migration tests.

Risks/open questions: providers may store sessions elsewhere; local store is an
index, not the source of provider truth.

### bd-1jh.25: Policy and Safety Layer

Goal: define library-level safety policy for cwd roots, additional directories,
tools, file writes, network-like controls, and approvals.

Affected modules: path handling, provider actions, command builders,
permissions, capabilities, docs.

Proposed model/API changes:

- Add policy models with allowed roots, allowed additional dirs, tool rules, and
  approval mode.
- Integrate with the execution policy layer from `bd-1jh.13`.

Task breakdown:

- Design policy schema and default stance.
- Implement cwd/additional-dir enforcement.
- Extend to tool/write/network-like controls where providers expose them.

Risks/open questions: network policy may only be expressible indirectly through
provider sandbox flags.

### bd-1jh.26: Versioned Event and Response Models

Goal: make normalized events/responses stable enough for downstream persistence
and UI integrations.

Affected modules: `api/events.py`, `api/models.py`, docs, fixtures, rendering.

Proposed model/API changes:

- Add schema version constants and serialized envelope metadata.
- Preserve existing Python class constructors.
- Document compatibility policy.

Task breakdown:

- Design versioning and serialization policy.
- Add version fields/helpers to events and responses.
- Update fixture/golden tests and docs.

Risks/open questions: adding fields to Pydantic models is compatible in Python
but can affect exact JSON snapshots.

### bd-1jh.27: Durable Trace Format

Goal: create a replayable trace artifact for debugging provider parser drift and
execution failures.

Affected modules: subprocess core, stream diagnostics, parser fixtures,
optional CLI flags, docs.

Proposed model/API changes:

- Add a trace model with execution metadata, normalized events, raw lines,
  stderr tail, diagnostics, and redaction metadata.
- Make trace capture opt-in at first.

Task breakdown:

- Design trace schema and redaction policy.
- Implement trace writing for execute and stream paths.
- Add trace docs and fixture tests.

Risks/open questions: raw provider payloads can include secrets; default
redaction must be conservative.

### bd-1jh.28: Replay-based Testing

Goal: feed recorded traces/fixtures through parser and reducer logic without
live provider CLIs.

Affected modules: tests/fixtures, tests/unit, parser contracts, trace format.

Proposed model/API changes:

- Add replay helpers under tests or a dev-only module.
- Keep production APIs independent from pytest.

Task breakdown:

- Design fixture/trace layout and replay runner.
- Convert existing provider fixtures to replay cases.
- Add CI/local test docs and regression assertions.

Risks/open questions: replay is most valuable after the trace format and parser
contract are defined.

### bd-1jh.29: Strict API/Engine/Bridge Boundaries

Goal: separate user facade, execution engine, parser layer, and provider
bridges more strictly.

Affected modules: `api`, `actions`, `services/core`, `services/bridges`, CLI,
tests.

Proposed model/API changes:

- Introduce a small execution engine boundary between actions and bridges.
- Keep provider bridges as command builder plus parser plus capability objects.

Task breakdown:

- Design module ownership and dependency direction.
- Extract engine interfaces without changing public facade.
- Move provider-specific leakage behind bridge boundaries.

Risks/open questions: this should happen after parser/reducer contracts are
settled to avoid moving unstable abstractions twice.

### bd-1jh.30: Multiple Output Modes From One Core Model

Goal: render the same normalized execution model as Python objects, JSONL,
compact CLI text, rich CLI output, and trace files.

Affected modules: CLI, events/responses, trace model, docs, tests.

Proposed model/API changes:

- Add renderer functions/classes for text, JSON, JSONL, and rich output.
- Keep Python object models as the source of truth.

Task breakdown:

- Design renderer contracts and CLI flags.
- Implement JSON/JSONL and compact text renderers.
- Add rich renderer and trace renderer integration.

Risks/open questions: renderer work should follow versioned models and trace
format so output modes do not freeze unstable contracts.

## Review Gate

The child implementation tasks created from this roadmap should stay blocked
until the roadmap is reviewed and the team chooses an execution order. The
recommended first implementation sequence is:

1. `bd-1jh.23` common parser contract.
2. `bd-1jh.18` shared stream/aggregate pipeline.
3. `bd-1jh.19` error taxonomy.
4. `bd-1jh.26` versioned event/response models.
5. `bd-1jh.27` durable trace format.
6. `bd-1jh.28` replay-based testing.

That sequence creates the foundation needed for the remaining model, policy,
session, cancellation, async, architecture, and renderer work.
