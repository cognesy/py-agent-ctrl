# Lessons From ACP for py-agent-ctrl

Last updated: 2026-05-09

## Context

The original purpose of `py-agent-ctrl` is a Python API for executing existing
CLI coding agents and consuming their outputs, including streamed outputs:

```python
response = AgentCtrl.codex().execute("Review this repository")

for event in AgentCtrl.claude_code().stream("Implement the plan"):
    ...
```

That purpose is different from ACP. ACP is a protocol for connecting clients and
ACP-native agents. Therefore, the current ACP adapter under
`libs/py_agent_ctrl/adapters/acp.py` is not a strong fit for the product
direction. `py-agent-ctrl` should not try to become an ACP implementation or
pretend existing non-ACP CLIs are ACP agents.

However, ACP and the Python SDK are still valuable as design references. They
show how to make agent control surfaces more explicit, typed, stream-safe,
permission-aware, cancellable, and durable.

This note lists improvements to implement in `py-agent-ctrl`, grouped by cost.

## Core Takeaway

Use ACP as a **design reference**, not as the `py-agent-ctrl` runtime contract.

Keep:

- direct CLI bridge abstraction;
- provider-specific command builders;
- provider-specific stream parsers;
- Python-first `AgentCtrl` facade;
- normalized `AgentRequest`, `AgentResponse`, and `AgentEvent` models.

Borrow from ACP:

- sharper lifecycle semantics;
- richer event vocabulary;
- explicit capabilities;
- tool-call lifecycle modeling;
- permission lifecycle modeling;
- cancellation semantics;
- filesystem/terminal guardrails;
- schema-backed tests and golden fixtures;
- transport/process hardening patterns.

## A. Low Hanging Fruits

These are small, mostly local changes that improve clarity and correctness
without changing the public API deeply.

### 1. Retire the ACP Adapter as a Public Concept

**Current state**

- `libs/py_agent_ctrl/adapters/acp.py` manually maps internal events into
  ACP-shaped dictionaries.
- The mapping is not real ACP, not schema-validated, and not useful for the
  direct Python API mission.

**Change**

- Remove or deprecate the ACP adapter module.
- Remove `tests/unit/test_acp_adapter.py` or rewrite it as internal event
  projection tests if any mapping remains useful.
- Preserve the research notes under `research/` as design references.

**Value**

- Removes a misleading integration surface.
- Prevents users or future agents from assuming `py-agent-ctrl` is ACP-compliant.
- Keeps the codebase focused on controlling existing CLI agents.

### 2. Rename ACP-inspired Internals to Provider-neutral Terms

**Current state**

- Some internal concepts overlap with ACP vocabulary but are not actually ACP
  protocol entities.

**Change**

- Prefer names like `NormalizedAgentEvent`, `NormalizedToolCall`,
  `ProviderCapability`, or `BridgeCapability` where appropriate.
- Avoid protocol-specific naming unless the code actually implements that
  protocol.

**Value**

- Makes the architecture easier to reason about.
- Reduces accidental coupling to a protocol that is not the runtime contract.

### 3. Add Explicit Event Discriminators and Stable Event Docs

**Current state**

- Events are Pydantic models with `type` fields, but the event contract is not
  documented as a first-class API.

**Change**

- Document each event type in `docs/user/quickstart.md` or a dedicated
  `docs/user/events.md`.
- State which events are stable and which fields may be provider-specific.
- Clarify that `raw` preserves provider-native payloads.

**Value**

- ACP's biggest practical strength is a clear event vocabulary.
- A stable event contract makes streaming usable by downstream developers.
- It helps prevent accidental breaking changes in parser refactors.

### 4. Normalize Tool Status Values

**Current state**

- `ToolCall.status` is an unconstrained `str | None`.
- Provider parsers may pass through provider-native statuses directly.

**Change**

- Introduce a `ToolCallStatus` enum:
  - `pending`
  - `in_progress`
  - `completed`
  - `failed`
  - `cancelled`, if needed for provider-native cancellation
- Map provider statuses into this enum while preserving raw status in `raw`.

**Value**

- Borrowed directly from ACP's status discipline.
- Makes UI rendering and automation logic predictable.
- Avoids each downstream user rediscovering provider-specific status strings.

### 5. Add Tool Kind Classification

**Current state**

- `ToolCall.name` exists, but there is no provider-neutral kind.

**Change**

- Add a `ToolKind` enum inspired by ACP:
  - `read`
  - `edit`
  - `delete`
  - `move`
  - `search`
  - `execute`
  - `think`
  - `fetch`
  - `other`
- Keep provider-native tool name separately.

**Value**

- Lets consumers group tools without knowing provider-specific names.
- Makes streamed displays cleaner.
- Improves filtering: for example, "show only edits and command execution."

### 6. Make Capabilities More Specific

**Current state**

- `BridgeCapabilities` has broad booleans:
  - `supports_streaming`
  - `supports_session_resume`
  - `supports_continue`
  - `supports_permissions`
  - `supported_options`

**Change**

- Add capability fields for concrete behaviors:
  - `supports_tool_events`
  - `supports_usage`
  - `supports_reasoning`
  - `supports_plan_events`
  - `supports_file_change_events`
  - `supports_permission_callbacks`
  - `supports_cancellation`
  - `supports_structured_json_output`

**Value**

- ACP shows the value of explicit capability negotiation.
- `py-agent-ctrl` does not need protocol negotiation, but callers still need to
  know what a bridge can actually emit.
- Prevents overpromising based on agent name alone.

### 7. Add Golden Fixture Tests for Provider Events

**Current state**

- Parser tests exist, but the contract can be strengthened.

**Change**

- Store representative provider output fixtures.
- Add golden tests for normalized event sequences and final responses.
- Include edge cases: malformed JSONL, partial lines, unknown event types,
  failed tool calls, tool-result pairing, empty text, and usage-only final
  events.

**Value**

- ACP SDK uses schema/golden discipline to keep helper output aligned with the
  protocol.
- `py-agent-ctrl` needs the same discipline for provider-native formats.
- This hardens the most fragile part of the library: stream parsing.

### 8. Preserve Stderr Tail and Parse Diagnostics in Streaming Results

**Current state**

- Aggregate responses carry parse diagnostics.
- Streaming currently exposes exit code but less diagnostic context.

**Change**

- Extend `StreamResult` to expose parse failures, skipped lines, stderr tail,
  timed-out state, and duration after exhaustion.

**Value**

- Developers using streamed APIs need the same failure diagnostics as
  non-streamed execution.
- Makes stream mode production-usable instead of demo-only.

### 9. Tighten Path Handling

**Current state**

- Requests accept `working_directory` and `additional_directories`.

**Change**

- Normalize paths early.
- Store resolved absolute paths in request execution state.
- Reject missing working directories before command execution.
- Document how additional directories are passed to each provider.

**Value**

- ACP treats workspace boundaries as part of the contract.
- This reduces accidental execution in the wrong directory.
- It makes provider command builders simpler and safer.

### 10. Document "What This Library Is Not"

**Current state**

- The ACP adapter can make the intended boundary ambiguous.

**Change**

- Add a short README/docs section:
  - not an ACP implementation;
  - not an agent framework;
  - not a tool server;
  - not a replacement for provider CLIs;
  - a Python control facade over installed CLI agents.

**Value**

- Prevents product drift.
- Sets correct expectations for contributors.
- Makes future design reviews easier.

## B. Medium Complexity Refactorings

These require coordinated model, parser, and test changes, but should not force
a full architecture rewrite.

### 1. Introduce a First-class Tool Call Lifecycle

**Current state**

- `AgentToolCallEvent` usually represents a whole tool call at one point in
  time.
- Some providers emit tool start and tool result separately, but the normalized
  model does not fully express that lifecycle.

**Change**

- Split tool events into lifecycle-aware variants or add a `phase` field:
  - `started`
  - `updated`
  - `completed`
  - `failed`
- Track stable tool IDs across provider start/result events.
- Add a small `ToolCallTracker` service to pair starts and results.

**Value**

- ACP's tool lifecycle is clearer than a single "tool happened" event.
- Downstream consumers can show accurate progress.
- Provider parsers become less ad hoc.
- Failed or incomplete tool calls become visible instead of getting lost.

### 2. Add a Structured Content Model

**Current state**

- Prompt input is a plain string.
- Event output is mostly plain text plus raw payloads.

**Change**

- Add internal content block models:
  - text;
  - file/resource reference;
  - image reference or bytes, if provider supports it;
  - structured diff;
  - terminal output reference.
- Keep `.execute("text")` and `.stream("text")` as the ergonomic API.
- Allow advanced users to pass a richer request object.

**Value**

- ACP demonstrates that agent IO is not always plain text.
- This gives `py-agent-ctrl` room to support images, file references, and rich
  tool output without provider-specific hacks.
- It preserves the simple API while adding a serious lower-level contract.

### 3. Rework PermissionBroker Into a Real Execution Policy Layer

**Current state**

- Permission models and `PermissionBroker` exist, but they are mostly detached
  from provider execution.

**Change**

- Introduce a provider-neutral `PermissionPolicy`:
  - allow all;
  - reject all;
  - prompt callback;
  - allow by tool kind/name;
  - allow by path scope;
  - provider-native mode passthrough.
- Wire provider command builders to policy where possible.
- Surface permission requests in streaming events when providers expose them.

**Value**

- ACP's permission flow is valuable because it treats permission as part of the
  turn lifecycle, not just a CLI flag.
- A real policy layer makes the Python API safer for automation.
- It creates a consistent abstraction over Claude permission modes, Codex
  sandboxing, Gemini approval modes, and future providers.

### 4. Add Cooperative Cancellation

**Current state**

- Timeouts can kill processes.
- There is no first-class cancellation token exposed to callers.

**Change**

- Add a cancellation handle for streaming executions.
- Support:
  - graceful stdin close where useful;
  - signal/terminate;
  - kill after grace period;
  - final stream drain/diagnostic capture.
- Mark final response/stream metadata as cancelled.

**Value**

- ACP's `session/cancel` is a semantic cancellation, not only process death.
- Python callers need to stop long-running agent work reliably.
- This is critical for interactive apps and batch orchestrators.

### 5. Separate Execution Identity From Provider Session Identity

**Current state**

- `execution_id`, `session_id`, `resume_session_id`, and `continue_session` are
  present but conceptually mixed.

**Change**

- Define:
  - `execution_id`: one local invocation;
  - `provider_session_id`: provider's conversation/session ID;
  - `conversation_id`: optional library-level continuity handle;
  - `trace_id`: optional cross-call correlation ID.
- Update responses and events to carry the right identity fields.

**Value**

- ACP makes session lifecycle explicit; `py-agent-ctrl` should do the same in a
  provider-native way.
- Prevents resume/continue bugs.
- Makes logs, traces, and retries easier to reason about.

### 6. Add a Normalized Terminal/Command Event Model

**Current state**

- Internal command execution exists for launching provider CLIs.
- Provider-emitted shell/command tool calls are represented as generic tool
  calls.

**Change**

- Add normalized command execution data:
  - command;
  - args;
  - cwd;
  - exit code;
  - stdout/stderr excerpts;
  - duration;
  - timed out flag.
- Map provider command tool calls into that structure when possible.

**Value**

- ACP's terminal model separates command execution from generic text.
- Developers consuming `py-agent-ctrl` frequently care about command failures.
- A typed command event makes automation more reliable.

### 7. Add File Change / Diff as a First-class Event

**Current state**

- There is `AgentFileChangeEvent`, but parsers sometimes model file changes as
  generic tool calls.

**Change**

- Normalize file edits into:
  - path;
  - action;
  - old text/new text where available;
  - unified diff where available;
  - provider raw event.
- Ensure Codex/Claude/Gemini mappings emit file-change events consistently.

**Value**

- ACP's file edit content variant is a useful design reference.
- Users of a coding-agent control library need to inspect edits programmatically.
- This enables "run agent, then review files touched" workflows.

### 8. Make Streaming and Aggregate Execution Share One Pipeline

**Current state**

- Bridges often have separate aggregate parsing and streaming parsing paths.

**Change**

- Use a single event pipeline:
  - command process emits raw lines;
  - parser emits normalized events;
  - reducer builds `AgentResponse`;
  - stream API yields events live;
  - execute API consumes the same stream and returns the reduced response.

**Value**

- ACP's prompt turn model has one stream of updates and one final response.
- A unified pipeline avoids divergence between `.execute()` and `.stream()`.
- It reduces duplicated parser bugs.

### 9. Improve Error Taxonomy

**Current state**

- Some subprocess errors and parse diagnostics exist, but the user-facing error
  model can be more explicit.

**Change**

- Add structured error categories:
  - binary missing;
  - auth/config missing;
  - working directory missing;
  - command timeout;
  - provider non-zero exit;
  - parse failure threshold exceeded;
  - unsupported option;
  - permission denied;
  - cancellation.

**Value**

- ACP formalizes stop reasons and request errors.
- `py-agent-ctrl` needs equivalent clarity for Python callers.
- Better errors reduce defensive string parsing by users.

### 10. Add Capability-driven Builder Validation

**Current state**

- Fluent builder methods can set options that may not apply to every provider.

**Change**

- Validate request options against bridge capabilities before execution.
- Return structured validation errors for unsupported combinations.
- Example: image input on a provider bridge that cannot pass images.

**Value**

- ACP capabilities prevent clients from sending unsupported payloads.
- `py-agent-ctrl` can apply the same principle without protocol negotiation.
- This catches mistakes before launching long-running CLIs.

## C. Deep Redesign Improvements

These changes reshape core abstractions. They are worth considering if
`py-agent-ctrl` is intended to become a durable execution substrate rather than
a thin wrapper.

### 1. Redesign Around an Internal Agent Turn State Machine

**Current state**

- Execution is mostly command-in, parsed-events-out.

**Change**

- Model each invocation as an `AgentTurn` with explicit states:
  - created;
  - command_built;
  - process_started;
  - streaming;
  - awaiting_permission;
  - cancelling;
  - completed;
  - failed;
  - cancelled;
  - timed_out.

**Value**

- ACP's prompt turn lifecycle is explicit and resilient.
- A state machine would make cancellation, permissions, partial results, and
  cleanup much easier to reason about.
- This is the foundation for robust orchestration and UI integration.

### 2. Introduce Async-native Execution

**Current state**

- Public execution is synchronous.
- Streaming is a synchronous iterator.

**Change**

- Add async equivalents:
  - `await execute_async(...)`;
  - `async for event in stream_async(...)`;
  - async cancellation handles;
  - async callbacks.
- Keep sync APIs as wrappers.

**Value**

- ACP Python SDK is async because agent/client streams are naturally async.
- Modern developer tools, web servers, notebooks, and orchestrators often need
  async integration.
- This avoids thread/queue glue becoming the hidden architecture.

### 3. Replace Provider-specific Stream Parsers With a Common Parser Contract

**Current state**

- Each bridge has parser functions with similar but not identical behavior.

**Change**

- Define a `ProviderEventParser` protocol:
  - consume raw line/chunk;
  - emit zero or more normalized events;
  - expose diagnostics;
  - finish/drain partial state.
- Implement each provider parser against that contract.

**Value**

- ACP SDK cleanly separates schema, router, and transport concerns.
- `py-agent-ctrl` should similarly separate raw transport, provider parsing,
  normalization, and response reduction.
- This makes adding new CLIs substantially safer.

### 4. Build a Session Store

**Current state**

- Session support is mostly passthrough to provider options.

**Change**

- Add an internal session store that tracks:
  - provider;
  - provider session ID;
  - cwd;
  - model/options;
  - last execution ID;
  - timestamps;
  - title/tags;
  - raw provider metadata.

**Value**

- ACP treats session lifecycle as a first-class concept.
- `py-agent-ctrl` users need practical session operations across providers.
- This unlocks reliable `.continue_session()`, `.resume_session(...)`,
  `.list_sessions()`, and cross-provider session introspection.

### 5. Introduce a Policy and Safety Layer

**Current state**

- Sandbox and permission options are provider-specific.

**Change**

- Add a library-level policy object:
  - allowed cwd roots;
  - allowed additional directories;
  - allowed commands/tool kinds;
  - file write policy;
  - network policy if providers expose it;
  - approval callback;
  - provider-specific lowering.

**Value**

- ACP's client/agent split makes permission and resource access explicit.
- `py-agent-ctrl` directly launches powerful local CLIs; it needs an equally
  explicit safety model.
- This is important for automation, CI, and multi-agent orchestration.

### 6. Make Event and Response Models Versioned

**Current state**

- Internal models are Python classes without an explicit schema/version contract.

**Change**

- Add a versioned normalized event schema.
- Include `schema_version` or library event-contract version in serialized
  events.
- Provide migration/deprecation rules for event fields.

**Value**

- ACP's schema versioning is a strong lesson.
- Downstream users may persist events or build UIs on them.
- Versioning prevents accidental breaking changes as providers evolve.

### 7. Add a Durable Trace Format

**Current state**

- Raw provider responses are preserved in some places, but there is no unified
  trace artifact.

**Change**

- Define a trace file format containing:
  - request;
  - command spec;
  - environment summary with secrets redacted;
  - raw stdout/stderr samples;
  - normalized events;
  - final response;
  - diagnostics;
  - timings.

**Value**

- ACP's structured event stream is inspectable and replayable.
- `py-agent-ctrl` needs replayable traces for debugging provider parser drift.
- This makes bug reports actionable without rerunning expensive agent calls.

### 8. Add Replay-based Testing

**Current state**

- Tests can validate selected parser examples.

**Change**

- Support replaying recorded traces through parser/reducer logic.
- Add a test fixture format for provider stream recordings.
- Verify stable normalized output from real-world provider sessions.

**Value**

- Provider CLIs change often.
- Replay tests catch parser regressions without invoking live CLIs.
- This is the equivalent of ACP schema/golden testing for a provider-wrapper
  library.

### 9. Separate User API, Execution Engine, and Provider Bridges More Strictly

**Current state**

- The code already has `api`, `actions`, and `services`, but more behavior can
  be pushed into a common execution engine.

**Change**

- Clarify layers:
  - facade/builder layer: user ergonomics;
  - action layer: use cases and validation;
  - execution engine: process lifecycle, streaming, cancellation, diagnostics;
  - parser layer: provider output normalization;
  - provider bridge layer: argv/env and provider-specific options.

**Value**

- ACP SDK is clean because protocol, schema, helpers, transports, and examples
  have clear responsibilities.
- `py-agent-ctrl` can get similar maintainability without adopting ACP runtime.
- It reduces provider-specific leakage into the public API.

### 10. Support Multiple Output Modes From One Core Model

**Current state**

- The main outputs are Python objects and CLI formatting.

**Change**

- Make normalized events/output renderable as:
  - Python objects;
  - JSONL;
  - compact CLI text;
  - rich CLI display;
  - trace files.

**Value**

- ACP's structured updates can be rendered many ways.
- A normalized internal model should let `py-agent-ctrl` serve library users,
  CLI users, and future automation tools without duplicating logic.

## Priority Recommendation

Do first:

1. Retire the ACP adapter as a public/runtime concept.
2. Normalize tool statuses and tool kinds.
3. Expand `BridgeCapabilities`.
4. Add golden provider fixture tests.
5. Expose richer streaming diagnostics.

Then:

1. Build a tool-call lifecycle tracker.
2. Introduce a real permission policy layer.
3. Unify streaming and aggregate execution around one event pipeline.
4. Add cooperative cancellation.
5. Clarify execution/session identity.

Only after that:

1. Move toward async-native execution.
2. Add a turn state machine.
3. Add durable traces and replay tests.
4. Build a real session store.
5. Add a deeper safety/policy layer.

## Bottom Line

The ACP adapter should be removed or demoted because it points in the wrong
direction for `py-agent-ctrl`.

The right lesson from ACP is not "support ACP." The right lesson is that a
serious agent-control library needs:

- explicit lifecycle;
- explicit capabilities;
- typed event vocabulary;
- structured tool lifecycle;
- permission and cancellation semantics;
- strong parser diagnostics;
- durable tests against real message shapes.

Those lessons apply directly to `py-agent-ctrl` while preserving its original
mission: a Python API for executing existing CLI coding agents.

