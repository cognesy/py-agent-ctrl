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
   Any code under `apps/` should parse args, call one adapter/action, and format
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
- `services/core/binaries.py`
- `services/core/env.py`
- `services/bridges/<provider>/models.py`
- `services/bridges/<provider>/bridge.py`
- `services/bridges/<provider>/command_builder.py`
- `services/bridges/<provider>/parser.py`

## Bridge Split

Each agent integration still has two concerns, but they live inside the
three-layer architecture:

1. direct bridge
   Provider-specific CLI integration in the services layer
2. normalized adapter behavior
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
│       │   ├── contracts.py        # Bridge / adapter protocols
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

Provider-specific adapters may expose extra fluent methods, but they should all
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
- define bridge and adapter contracts
- add execution ID distinct from provider session ID
- define common error types and parse diagnostics

### Phase 3. Extract Claude Code Into Bridge + Adapter

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
  Pydantic models, command builders, parsers, adapters
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
common adapter API. When it needs provider-only controls, it should still use
the provider adapter, but receive the same normalized response models.

That gives this repo the right split:

- direct bridge = stable place for raw CLI behavior
- common adapter = stable place for client-facing portability

This is the architecture to implement.
