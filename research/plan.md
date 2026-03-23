# Refactoring Plan

## Core Architectural Decision

This repo should follow the same structural pattern used across the other
projects:

- command layer
- invokeable actions layer
- service layer

For `py-agent-ctrl`, this pattern is applicable and should be made explicit.

## Layer Mapping For This Repo

### Command Layer

The command layer contains thin entry points only.

Examples:

- `apps/cli/` for the unified `ctrlagent` CLI
- the public Python-facing facade as an import surface

Responsibilities:

- parse args or request inputs
- choose the target agent
- call one action
- format output for CLI or Python callers

Non-responsibilities:

- subprocess orchestration
- provider-specific stream parsing
- business logic around request normalization

## Actions Layer

The actions layer owns use cases.

Examples:

- execute a prompt
- stream a prompt
- continue the latest session
- resume a specific session
- inspect bridge capabilities
- list supported agents

Responsibilities:

- accept normalized request models
- orchestrate one or more services
- normalize provider-specific outputs into common API models
- enforce common semantics across agents where possible

This is where the common API belongs.

## Service Layer

The service layer owns actual implementation details.

Examples:

- subprocess execution
- CLI binary discovery
- argv construction
- env preparation
- stream-json / JSONL parsing
- provider-specific request and event handling

This is also where direct agent bridges belong.

## Bridge Split

Each supported agent should have two distinct concerns:

1. direct bridge
   Provider-specific CLI integration in the service layer
2. common adapter
   Normalized mapping into the common API at the actions layer

That means the architecture is not just "bridge and adapter". The more complete
shape is:

`command -> actions -> services`

with:

- direct bridge in services
- normalized adapter behavior in actions

## Why `apps/cli/` Is Justified

If we bundle a unified `ctrlagent` command line that can invoke any supported
agent through one interface, then `apps/cli/` is not incidental. It becomes the
correct command-layer home.

`ctrlagent` should be thin and should delegate to actions.

Possible CLI commands:

- `ctrlagent execute`
- `ctrlagent stream`
- `ctrlagent continue`
- `ctrlagent resume`
- `ctrlagent agents list`
- `ctrlagent agents capabilities`

The CLI should not know how to parse provider stream payloads or build provider
argv directly. That stays below the action boundary.

## Recommended Target Layout

```text
apps/
  cli/
    main.py
    cmd_execute.py
    cmd_stream.py
    cmd_sessions.py
    cmd_agents.py

libs/
  py_agent_ctrl/
    api/
      models.py
      events.py
      ids.py
      capabilities.py
      facade.py
    actions/
      execute.py
      stream.py
      sessions.py
      agents.py
    services/
      core/
        subprocess.py
        binaries.py
        env.py
      bridges/
        claude_code/
        codex/
        opencode/
        pi/
        gemini/
```

## Public API Direction

The repo should expose both:

- a Python import API
- a unified `ctrlagent` CLI

Both should call the same actions layer.

Examples:

```python
from py_agent_ctrl import AgentCtrl

response = AgentCtrl.claude_code().execute("Summarize this repository.")
```

```bash
ctrlagent execute --agent claude-code "Summarize this repository."
ctrlagent execute --agent codex "Write a refactoring plan."
```

## Agent Scope

The planned bridge inventory remains CLI-only:

- Claude Code
- Codex
- OpenCode
- Pi
- Gemini CLI

Cursor is out of scope because it is not a CLI target for this repo.

## Modeling Rules

- all structured data models should be Pydantic
- provider-specific request and event models should also be Pydantic
- normalized response and event models should be Pydantic
- use `uv` only for Python execution and tooling

## Migration Rule

This migration is a clean cut to the new structure.

That means:

- move implementation to `libs/py_agent_ctrl/`
- remove the legacy root `./agent_ctrl` layout once parity is reached
- do not keep `ClaudeCodeClient` as a compatibility shim
- handle downstream migration through docs and upgrade guidance rather than
  parallel in-repo architectures
- use `py_agent_ctrl` as the canonical Python import root to avoid package-name
  clashes with other libraries

## Immediate Next Steps

1. Update `docs/dev/architecture.md` so it explicitly reflects
   `command -> actions -> services`.
2. Introduce the new `libs/py_agent_ctrl/` package skeleton.
3. Extract Claude Code first into the new service bridge and action adapter
   shape, then remove the legacy flat implementation.
4. Add the `apps/cli/` skeleton for `ctrlagent`.
5. Port the remaining agent bridges after the common action/API layer is stable.
