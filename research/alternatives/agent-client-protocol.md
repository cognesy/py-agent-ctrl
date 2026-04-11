# Agent Client Protocol

Local references:

- `/Users/ddebowczyk/projects/_ext/agent-client-protocol`
- `/Users/ddebowczyk/projects/_ext/agent-client-protocol-python-sdk`

## Fit

ACP is not a direct CLI wrapper. It is a protocol for connecting clients/editors
to agents over JSON-RPC. It is useful as a future interoperability target and as
a vocabulary for events, permissions, terminals, and session state.

## Relevant Design

Protocol surface:

- `schema/schema.json` defines `session/new`, `session/load`, `session/prompt`,
  `session/cancel`, and `session/update`.
- Client callbacks include `session/request_permission`, filesystem methods,
  and `terminal/*` methods.
- `session/update` is a notification stream, not a response payload.
- The schema explicitly says clients should still accept tool-call updates after
  cancellation because agents may send final updates before returning the
  cancelled stop reason.

Content/event model:

- ACP uses content blocks rather than plain strings.
- Session updates include user message chunks, agent message chunks, agent
  thought chunks, plan updates, tool-call start/progress, available commands,
  current mode, session info, and usage updates.
- Tool calls can include content, file edits, terminal references, locations,
  raw input, and raw output.

Permissions:

- Permission requests are tied to a session and a tool call.
- Permission options have IDs and kinds such as allow-once, allow-always, and
  reject-once.
- Cancellation requires resolving pending permission requests with a cancelled
  outcome.

Terminal delegation:

- ACP lets an agent ask the client to create a terminal, read output, wait for
  exit, kill a command, and release the terminal.
- This is an important distinction: sandboxed execution can be modeled as a
  client capability, not only as local subprocess control inside the agent.

Python SDK:

- `src/acp/transports.py` implements defensive stdio subprocess launching with a
  trimmed inherited environment, graceful stdin close, terminate, and kill.
- `src/acp/stdio.py` wraps spawned stdio processes into agent/client-side
  connections.
- `src/acp/contrib/session_state.py` accumulates session notifications into a
  snapshot and handles session changes.
- `src/acp/contrib/tool_calls.py` tracks tool call lifecycle and emits start and
  progress models.
- `src/acp/contrib/permissions.py` provides a permission broker with standard
  options.
- `examples/gemini.py` shows how an ACP client can auto-approve or prompt for
  permissions, enforce absolute paths for filesystem calls, create terminals,
  and run Gemini with `--experimental-acp`.

## What To Borrow

- Treat our current `AgentEvent` union as a minimal layer, not the final event
  model. ACP has a better vocabulary for plans, thoughts, tool progress, usage,
  modes, and terminals.
- Add an internal `ToolCallTracker` concept when providers emit tool start and
  tool result separately.
- Add a permission broker shape that ties permission requests to normalized tool
  calls and has standard option kinds.
- Add cancellation semantics that include resolving pending permission requests.
- Use explicit capability metadata: filesystem, terminal, session load, prompt,
  streaming, permission, and sandbox support.
- Keep all paths absolute for protocol-facing APIs, matching ACP guidance.

## What Not To Copy Directly

- Do not make ACP the core runtime dependency yet. Most target CLIs still emit
  provider-native JSONL or TUI/transcript formats.
- Do not force `py-agent-ctrl` users to implement a JSON-RPC client/server just
  to run `AgentCtrl.codex().execute(...)`.
- Treat ACP as an adapter target: `py-agent-ctrl` could project normalized
  events into ACP session updates later.

## Gaps Relative To py-agent-ctrl

`py-agent-ctrl` lacks a typed capability model beyond a few booleans, lacks
permission and terminal abstractions, and does not distinguish content block
types. ACP suggests a path to grow without inventing an incompatible vocabulary.

## Experimental Projection Notes

`py-agent-ctrl` includes a lightweight, dependency-free projection helper in
`libs/py_agent_ctrl/adapters/acp.py`. It maps normalized events to ACP-like
session update dictionaries for experimentation.

Known unsupported or partial mappings:

- It does not implement JSON-RPC transport, an ACP server, or an ACP client.
- It does not add `agent-client-protocol` as a runtime dependency.
- Terminal delegation is not implemented.
- Permission requests are modeled separately but are not projected into ACP
  request/response traffic.
- Modes, available commands, and full content block annotations are not
  represented yet.
- File change events are projected as simple completed edit-like tool calls,
  not full ACP file edit content variants.
