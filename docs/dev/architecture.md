# py-agent-ctrl Architecture and Refactoring Plan

## Design Direction

This repository should converge on the same top-level conventions used across the
reference repos:

- `apps/` for thin runnable shells
- `libs/` for reusable importable code
- `resources/` for passive assets
- `docs/` for developer and user documentation
- `tests/` for clearly separated test layers

It should also catch up with the supported bridge inventory in
`~/projects/instructor-php/packages/agent-ctrl`, which currently targets these
CLI coding agents:

- Claude Code (`claude`)
- OpenAI Codex (`codex`)
- OpenCode (`opencode`)
- Pi (`pi`)
- Gemini CLI (`gemini`)

Cursor is out of scope here because the target for this repo is CLI-based coding
agents only.

## Hard Rules

1. CLI agents only
   The direct integration layer talks to subprocess CLIs only. Do not build this
   repo around vendor SDKs or in-process Python agent libraries.
2. Three explicit layers
   The repo follows the same command -> actions -> services split used across
   the user's other projects.
3. Pydantic models are the schema
   All structured requests, responses, events, tool calls, usage objects, and
   capability objects should be Pydantic models.
4. Unique Python package root
   Use `py_agent_ctrl` as the package root to avoid clashes with other Python
   libraries. Do not build the new architecture under a generic root such as
   `agent_ctrl`.
5. `uv` only
   Use `uv` for dependency management, execution, linting, and tests.
6. Apps are thin
   Any code under `apps/` should parse args, call one facade/action, and format
   output. No agent logic belongs there.
7. Resources stay passive
   Skills, example prompts, sample event payloads, and migration assets live
   under `resources/`; parsing and orchestration live under `libs/`.

## Why CLI-Only Is The Best Fit

Even when a vendor also ships a Python SDK, the coding-agent behavior we care
about is usually defined at the CLI boundary:

- session continuation and resume semantics
- sandbox and approval controls
- tool invocation behavior
- stream-json / JSONL event formats
- working-directory and additional-directory handling

Keeping the direct bridge strictly CLI-based gives this repo:

- parity with the PHP `agent-ctrl` package
- one execution model across all supported agents
- simpler docs and migration guidance
- fewer feature gaps between providers

If a CLI happens to be implemented in Python, that does not change the design:
we still treat it as an external CLI bridge.

## Layer Model

### 1. Command Layer

The command layer contains thin delivery surfaces only.

Responsibilities:

- parse CLI or Python-facing inputs
- choose one action
- invoke the action layer
- format output for the selected delivery surface

Non-responsibilities:

- subprocess execution
- provider-specific parsing
- bridge-specific normalization logic

Examples:

- `apps/cli/`
- the public Python facade under `libs/py_agent_ctrl/api/`

### 2. Actions Layer

The actions layer owns invokeable use cases and the normalized API.

Responsibilities:

- accept normalized request models
- orchestrate bridge and core services
- normalize provider-specific outputs into common response and event models
- expose use cases such as execute, stream, resume, continue, and capabilities
- keep provider-specific behavior isolated behind explicit action inputs

Non-responsibilities:

- raw subprocess management
- provider-native JSONL parsing
- CLI argv construction

Typical files:

- `api/models.py`
- `api/events.py`
- `api/contracts.py`
- `api/facade.py`
- `actions/execute.py`
- `actions/stream.py`
- `actions/sessions.py`
- `actions/agents.py`

### 3. Services Layer

The services layer owns implementation details, including the direct bridges.

Responsibilities:

- binary discovery
- argv and environment construction
- subprocess execution
- stdout/stderr and JSONL parsing
- provider-native request/event/capability models
- provider-specific bridge behavior

Non-responsibilities:

- public API shaping for callers
- command-line presentation
- pretending all provider features are portable

Typical files:

- `services/core/subprocess.py`
- `services/core/parsing.py`
- `services/core/pipeline.py`
- `services/core/binaries.py`
- `services/core/env.py`
- `services/bridges/<provider>/models.py`
- `services/bridges/<provider>/bridge.py`
- `services/bridges/<provider>/command_builder.py`
- `services/bridges/<provider>/parser.py`

## Internal Parser Contract

Provider JSONL parsing has a shared internal contract under
`services/core/parsing.py`.

The contract is deliberately internal:

- it is not ACP support
- it is not a public wire protocol
- it does not replace provider-native CLI formats
- it does not make provider event semantics portable when the providers differ

Its job is to keep the repeated mechanics in one place:

- consume JSONL stdout with bounded parse diagnostics
- retain raw provider payloads for `AgentResponse.raw_response`
- call the provider-specific `parse_*_events(...)` mapper
- pass normalized events and raw payloads into the provider-specific response
  reducer
- expose stream diagnostics through `StreamResult.diagnostics`

Provider packages still own provider meaning. Their `parser.py` modules decide
how native records become `AgentEvent` instances and how aggregate events become
`AgentResponse` fields such as text, session ID, usage, cost, and tool calls.
Their `bridge.py` modules own CLI command execution and any provider-specific
stream behavior that cannot be represented by a single raw payload. Gemini's
stream-time `tool_use` / `tool_result` pairing is the current example.

Fixture tests under `tests/fixtures/<provider>/` and
`tests/unit/test_provider_fixtures.py` are the regression contract for this
layer. New providers or parser changes should add replayable JSONL fixtures
before changing bridge behavior.

## Tool-call Lifecycle

Tool-call lifecycle support is an internal normalization aid, not a separate
wire protocol. `ToolCall.status` remains the normalized provider outcome, while
`ToolCall.phase` and `AgentToolCallEvent.phase` describe whether the record is a
start, update, terminal state, or honest provider snapshot.

The lifecycle phases are:

- `started`
- `updated`
- `completed`
- `failed`
- `cancelled`
- `snapshot`

The bridge should only claim the lifecycle granularity that the provider exposes.
Claude Code can surface a pending start. Gemini aggregate reduction tracks
`tool_use` and `tool_result` internally, while live streaming preserves the
existing paired-result behavior. Codex, OpenCode, and Pi mostly expose final
records, so their phases are inferred from status or left as `snapshot` when the
status is provider-specific.

Shared lifecycle merging lives in `services/core/tool_calls.py`. It exists to
avoid provider reducers hand-rolling partial start/result merging. It does not
make provider-native formats interchangeable, and it does not introduce support
for any external protocol runtime.

## Structured Content

Structured content is additive to the Python API. `AgentRequest.prompt` remains
the string compatibility surface, while `AgentRequest.content` can carry typed
blocks for richer callers. Command builders must call
`services/core/content.py::request_prompt_text(...)` instead of reading
`request.prompt` directly so every provider receives the same deterministic
fallback text.

The current content block vocabulary covers:

- text
- resource links
- embedded resources
- image references or data
- diffs
- terminal references

Provider-native lowering must be explicit and conservative. Codex image
references are lowered to the existing `--image` flag. Other providers keep the
plain-text fallback until their CLI-specific support is researched and tested.
Do not dereference remote resources or inline raw blobs into argv by default.

## Internal Execution Pipeline

Provider execution has a shared internal pipeline under
`services/core/pipeline.py`.

The pipeline owns the repeated flow that used to live in every bridge:

1. parse aggregate stdout or streamed JSONL records;
2. record valid raw provider payloads;
3. emit normalized provider events through the parser contract;
4. keep parse diagnostics attached to the execution state;
5. reduce accumulated state through the provider reducer;
6. expose stream diagnostics through `StreamResult`.

The bridge still owns provider command construction and provider-specific
stream behavior. The pipeline intentionally does not know how to build a Codex,
Claude, Gemini, OpenCode, or Pi command. It receives a `CommandSpec` and a
provider parser/reducer pair.

Most providers use the default stream behavior: yield the same normalized
events that are stored in the execution state. Providers that need different
live stream emission can pass a narrow stream payload adapter. Gemini uses this
for live `tool_use` / `tool_result` pairing while the pipeline still records
the original raw payloads and parser events for aggregate reduction.

## Bridge Split

Each agent integration still has two concerns, but they live inside the
three-layer architecture:

1. direct bridge
   Provider-specific CLI integration in the services layer
2. normalized facade behavior
   Action-layer mapping into the common API

The implementation contract is therefore:

`command -> actions -> services`

## Recommended Repository Layout

```text
py-agent-ctrl/
├── apps/
│   └── cli/                         # Thin smoke-test / demo / ops CLI
│
├── docs/
│   ├── dev/
│   │   └── architecture.md
│   └── user/                        # End-user docs, migration guides, examples
│
├── libs/
│   └── py_agent_ctrl/
│       ├── __init__.py
│       ├── api/
│       │   ├── models.py           # Pydantic common request/response models
│       │   ├── events.py           # Pydantic normalized event models
│       │   ├── ids.py              # Execution/session/tool-call IDs
│       │   ├── contracts.py        # Bridge protocols
│       │   ├── capabilities.py     # Common capability model
│       │   └── facade.py           # AgentCtrl facade
│       │
│       ├── actions/
│       │   ├── execute.py
│       │   ├── stream.py
│       │   ├── sessions.py
│       │   └── agents.py
│       │
│       └── services/
│           ├── core/
│           │   ├── config.py
│           │   ├── errors.py
│           │   ├── binaries.py
│           │   ├── env.py
│           │   └── subprocess.py
│           └── bridges/
│               ├── claude_code/
│               │   ├── models.py
│               │   ├── bridge.py
│               │   ├── command_builder.py
│               │   └── parser.py
│               ├── codex/
│               ├── opencode/
│               ├── pi/
│               └── gemini/
│
├── resources/
│   └── skills/
│       └── upgrade/
│           └── SKILL.md
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── feature/
│   └── regression/
│
├── pyproject.toml
└── README.md
```

## Public API Direction

The Python package should keep a simple top-level facade, aligned with the PHP
package but expressed in Python naming:

```python
from py_agent_ctrl import AgentCtrl

response = AgentCtrl.claude_code().execute("Summarize this repository.")
response = AgentCtrl.codex().execute("Write a refactoring plan.")
response = AgentCtrl.gemini().execute("Review the tests.")
```

The normalized API should use Pydantic models for:

- `AgentResponse`
- `AgentRequest`
- `AgentTextEvent`
- `AgentToolCall`
- `TokenUsage`
- `BridgeCapabilities`

Provider-specific facades may expose extra fluent methods, but they should all
terminate in the same normalized response shape.

## Migration Strategy

This refactor is a clean cut to the new layout.

The current flat package under `./agent_ctrl` is legacy structure, not a target
surface to preserve. The implementation should move into `libs/py_agent_ctrl/`,
and the old root-level layout should be removed once the new structure is in
place.

That means:

1. no compatibility shim rooted in `./agent_ctrl`
2. no requirement to preserve `ClaudeCodeClient`
3. no requirement to keep dataclass-based event or response models
4. downstream migration is handled through updated docs and upgrade guidance,
   not parallel in-repo architectures
5. the canonical Python import root after migration is `py_agent_ctrl`

The target public API is simply:

```python
from py_agent_ctrl import AgentCtrl
```

## Bridge Inventory To Support

### Claude Code

Current repo functionality already covers a subset of this bridge:

- prompt execution
- streaming text/tool events
- session resume and continue
- permission mode
- additional directories

This should be the first bridge extracted into the new layout.

### Codex

Catch up with PHP support for:

- sandbox modes
- approval / bypass modes
- image input
- session/thread continuity
- normalized file change, bash, MCP, web-search, and reasoning items

### OpenCode

Catch up with PHP support for:

- provider-prefixed models
- named agents
- file attachments
- session sharing and titles
- usage and cost reporting

### Pi

Catch up with PHP support for:

- provider and model selection
- thinking levels
- tool allowlists
- skill loading
- extension loading
- session directory controls
- usage and cost reporting

### Gemini

Catch up with PHP support for:

- approval modes
- sandbox flag
- extensions
- allowed MCP servers
- policy files
- allowed tools
- session continuation
- usage reporting

## Refactoring Phases

### Phase 1. Create The New Skeleton

- add `docs/dev`, `docs/user`
- add `tests/unit`, `tests/integration`, `tests/feature`, `tests/regression`
- create `libs/py_agent_ctrl/`
- wire packaging directly to the new layout
- plan removal of the legacy root `agent_ctrl/` tree as part of the migration

### Phase 2. Introduce Common Pydantic API Models

- define normalized request, response, event, usage, and tool-call models
- define bridge and facade/action contracts
- add execution ID distinct from provider session ID
- define common error types and parse diagnostics

### Phase 3. Extract Claude Code Into Bridge + Facade

- move Claude-specific command building and parsing into
  `services/bridges/claude_code/`
- expose Claude through normalized actions and the common facade
- remove the old flat Claude implementation once parity is reached
- migrate existing tests to the new `tests/unit` layout

### Phase 4. Add The Common Facade

- implement `AgentCtrl.claude_code()`
- implement `AgentCtrl.codex()`
- implement `AgentCtrl.opencode()`
- implement `AgentCtrl.pi()`
- implement `AgentCtrl.gemini()`

Builders can be added incrementally, but the facade shape should be fixed
early.

### Phase 5. Port Remaining Bridges

Port in the order that minimizes migration risk:

1. Claude Code parity
2. Codex
3. Gemini
4. OpenCode
5. Pi

The order above favors the highest-likelihood Python demand while still keeping
the architecture ready for all five agents from the start.

### Phase 6. Expand Tests

- `tests/unit/`
  Pydantic models, command builders, parsers, facade/action contracts
- `tests/integration/`
  subprocess execution against real or stubbed CLIs
- `tests/feature/`
  end-to-end bridge flows from facade to normalized response
- `tests/regression/`
  frozen payloads for stream parsing and migration regressions

## Testing Policy

Use `uv` only. Examples:

- `uv run pytest tests/unit`
- `uv run pytest tests/integration`
- `uv run ruff check .`

Do not recommend or document direct `python`, `python3`, `pip`, or `pip3`
commands in this repo.

## Migration Guidance Summary

When downstream code only needs a coding agent result, it should prefer the
common facade/action API. When it needs provider-only controls, it should still
use the provider-specific facade methods, but receive the same normalized
response models.

That gives this repo the right split:

- direct bridge = stable place for raw CLI behavior
- common facade/action API = stable place for client-facing portability

This is the architecture to implement.
