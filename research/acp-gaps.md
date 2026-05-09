# ACP Fit-Gap Analysis for py-agent-ctrl

Last updated: 2026-05-09

## Scope

This note analyzes the current `py-agent-ctrl` implementation against full
Agent Client Protocol support, with the explicit direction that
`py-agent-ctrl` should use the local `acp-python-sdk`/`agent-client-protocol`
package rather than reimplementing ACP schema, JSON-RPC routing, or stdio
framing from scratch.

Primary local references:

- `py-agent-ctrl`: `/Users/ddebowczyk/projects/_libs/py-agent-ctrl`
- ACP SDK: `/Users/ddebowczyk/projects/_ext/acp-python-sdk`
- Current `py-agent-ctrl` ACP adapter:
  `libs/py_agent_ctrl/adapters/acp.py`
- Current ACP overview note:
  `research/acp.md`

## Executive Summary

`py-agent-ctrl` currently has an **ACP-shaped event projection**, not an ACP
implementation.

The existing adapter converts internal `AgentEvent` objects into dictionaries
that resemble ACP `session/update` payloads. It does not expose an ACP agent
server, connect to ACP clients, launch ACP agents, implement JSON-RPC message
exchange, negotiate capabilities, manage ACP sessions, respond to ACP prompt
requests, support client filesystem/terminal callbacks, or validate emitted
payloads against ACP schema models.

The shortest credible path is to keep `py-agent-ctrl` as the direct subprocess
library and add an optional ACP layer built on `agent-client-protocol`:

1. Add `agent-client-protocol` as an optional dependency.
2. Replace ad hoc ACP-shaped dicts with SDK Pydantic models and helper
   builders.
3. Implement an `acp.Agent` wrapper around `py-agent-ctrl` bridges.
4. Use `acp.run_agent()` for the ACP server entrypoint.
5. Optionally implement an `acp.Client` wrapper for driving external ACP agents
   through `spawn_agent_process()`.

## Current Implementation

### Public Control Model

`py-agent-ctrl` is organized around direct bridge execution:

- `AgentBridge` protocol has only `capabilities()`, `execute()`, and
  `stream()` methods.
- `AgentRequest` is prompt-centric: `prompt`, model/system prompt fields,
  working directory, additional directories, timeout, sandbox driver, session
  resume/continue flags, and provider options.
- `AgentResponse` is aggregate result-centric: text, exit code, execution ID,
  session ID, usage, cost, tool calls, raw response, parse diagnostics, and
  duration.
- `StreamResult` is a synchronous iterator over normalized internal events.

This is a good shape for controlling existing CLIs. It is not yet an ACP
request/response runtime.

### Internal Event Model

Current normalized events are:

- `AgentTextEvent`
- `AgentToolCallEvent`
- `AgentResultEvent`
- `AgentReasoningEvent`
- `AgentPlanUpdateEvent`
- `AgentUsageEvent`
- `AgentWarningEvent`
- `AgentFileChangeEvent`
- `AgentUnknownEvent`

This overlaps with ACP `session/update`, but it is narrower and less structured:

- no first-class content block union;
- no `user_message_chunk`;
- no separate `tool_call` start vs `tool_call_update` progress/result event;
- no `available_commands_update`;
- no `current_mode_update`;
- no `config_option`;
- no ACP-shaped `SessionInfoUpdate`;
- no terminal reference content;
- no ACP file-edit content variant.

### Existing ACP Adapter

`libs/py_agent_ctrl/adapters/acp.py` currently provides two functions:

- `event_to_acp_update(event) -> dict | None`
- `session_notification(session_id, event) -> dict | None`

It maps:

- text -> `agent_message_chunk`
- reasoning -> `agent_thought_chunk`
- tool call -> `tool_call`
- plan update -> `plan`
- usage -> `usage`
- warning -> `agent_message_chunk` plus warning-like annotation
- file change -> completed edit-like `tool_call`
- result -> `session_info`

Important limitations:

- uses snake_case keys such as `session_update`, `tool_call_id`, and
  `raw_input`, while ACP schema fields use names like `sessionUpdate`,
  `toolCallId`, and `rawInput` when serialized by the SDK;
- returns raw dictionaries, not `acp.schema` Pydantic models;
- does not validate against the ACP schema;
- does not wrap the update in a JSON-RPC notification;
- does not call `Client.session_update`;
- does not implement any ACP `Agent` methods;
- does not implement any ACP `Client` callbacks;
- has tests only for dictionary projection, not protocol compliance.

### Dependency State

`pyproject.toml` currently depends only on:

- `pydantic>=2.11`

It does not depend on:

- `agent-client-protocol`
- any JSON-RPC transport package
- any ACP schema package

Because the desired direction is to use `acp-python-sdk`, the main dependency
gap is to add `agent-client-protocol` directly or behind an extra such as
`py-agent-ctrl[acp]`.

## ACP Target Surface

The local ACP SDK provides the pieces `py-agent-ctrl` should consume:

- `acp.Agent` and `acp.Client` protocols;
- `acp.run_agent()` and `acp.connect_to_agent()`;
- `acp.spawn_agent_process()` and `acp.spawn_client_process()`;
- generated `acp.schema` Pydantic models;
- helpers such as `text_block`, `resource_link_block`, `start_tool_call`,
  `update_tool_call`, `update_agent_message`, `update_agent_thought`,
  `update_plan`, `tool_diff_content`, and `tool_terminal_ref`;
- stdio transport/environment helpers;
- contrib utilities for session state, tool calls, and permissions.

Full ACP support in `py-agent-ctrl` means supporting at least:

- `initialize`
- `session/new`
- `session/prompt`
- `session/cancel`
- `session/update`

Useful optional support includes:

- `session/list`
- `session/resume`
- `session/close`
- `session/set_mode`
- `session/set_model`
- `session/set_config_option`
- `session/request_permission`
- `fs/read_text_file`
- `fs/write_text_file`
- `terminal/create`
- `terminal/output`
- `terminal/wait_for_exit`
- `terminal/kill`
- `terminal/release`

## Fit-Gap Matrix

| ACP area | Current fit | Gap |
| --- | --- | --- |
| Schema models | Internal Pydantic models exist for requests, responses, events, usage, tools, and permissions | No use of generated `acp.schema`; current dict keys are not ACP model fields |
| Transport | Direct subprocess executor and line streaming exist | No ACP JSON-RPC framing, no `run_agent`, no `connect_to_agent`, no ACP stdio server/client |
| Agent role | Bridges can execute or stream prompts into provider CLIs | No `acp.Agent` implementation for `initialize`, `session/new`, `session/prompt`, cancellation, or session lifecycle |
| Client role | Direct bridge launcher can spawn local CLIs | No `acp.Client` implementation for receiving `session/update`, permissions, filesystem, or terminal requests from external ACP agents |
| Sessions | Provider session IDs are captured in some responses | No ACP session registry mapping ACP session IDs to `AgentRequest`, bridge choice, cwd, model, provider state, and provider session IDs |
| Prompt content | `AgentRequest.prompt` is a string | No support for ACP content blocks, resource links, embedded context, image, or audio |
| Streaming output | `StreamResult` yields normalized events | No async ACP notification stream through `Client.session_update`; no prompt response stop-reason semantics |
| Tool calls | `ToolCall` model captures id/name/arguments/output/status/error | No lifecycle separation between tool start/progress/completion; no ACP content variants, locations, terminal refs, or schema-normalized statuses/kinds |
| Permissions | `PermissionRequest`, `PermissionResponse`, and `PermissionBroker` exist | Not wired to provider execution or ACP `session/request_permission`; includes non-ACP `abort` option kind |
| Filesystem callbacks | Working directory and additional directories exist | No ACP client-side `fs/read_text_file` or `fs/write_text_file` implementation |
| Terminal callbacks | Host subprocess execution exists internally | No ACP client-side terminal service with terminal IDs, output polling, wait, kill, release, or terminal references |
| Capabilities | `BridgeCapabilities` is provider-oriented | No ACP `ClientCapabilities`/`AgentCapabilities` negotiation or capability derivation |
| Cancellation | Timeouts exist in subprocess executor | No explicit ACP `session/cancel` semantics, cooperative bridge cancellation, permission cancellation, or `stopReason="cancelled"` handling |
| MCP | Provider options include Claude/Gemini MCP config-style fields | No ACP `mcp_servers` handling from `session/new`, `session/load`, `session/resume`, or `session/fork` |
| Validation | Unit tests verify current projection dicts | No schema validation, golden ACP payload tests, or loopback tests with an ACP client |
| Packaging | Simple runtime dependency set | No optional `acp` extra or direct SDK dependency |

## Recommended Architecture Using acp-python-sdk

### Keep Existing Core

Do not replace the direct CLI abstraction. Keep:

- provider bridge command builders;
- provider parsers;
- `AgentCtrl` facade;
- `AgentBridge`;
- `AgentRequest`/`AgentResponse`;
- normalized internal events.

ACP should be an optional protocol-facing adapter around that core.

## Conceptual Overlap and Delegation Boundary

ACP and `py-agent-ctrl` overlap most strongly at the **agent/client boundary**:
both care about prompts, sessions, streamed updates, tool calls, permissions,
capabilities, filesystem access, terminal execution, and cancellation. They do
not overlap much at the **provider bridge boundary**: ACP does not know how to
invoke Claude Code, Codex, OpenCode, Pi, or Gemini in their native modes, parse
their provider-specific JSONL/transcript/TUI output, or translate their flags
and session IDs.

The practical split is:

- ACP SDK can own protocol mechanics and typed wire contracts.
- `py-agent-ctrl` must continue owning provider integration and normalized
  provider semantics.
- The adapter layer owns mapping between those worlds.

### Responsibilities ACP SDK Can Take Over

These responsibilities should be delegated to `agent-client-protocol` rather
than implemented in `py-agent-ctrl`:

| Responsibility | Delegate to ACP SDK? | Notes |
| --- | --- | --- |
| JSON-RPC request/response framing | yes | Use `run_agent`, `connect_to_agent`, and stdio helpers. |
| Stdio ACP transport lifecycle | yes | Use SDK transport helpers instead of custom ACP pipes. |
| Generated protocol models | yes | Use `acp.schema` instead of local duplicate ACP DTOs. |
| Field aliases/discriminators | yes | Use SDK models/helpers so `sessionUpdate`, `toolCallId`, etc. stay correct. |
| Agent/client method routing | yes | Implement SDK `Agent`/`Client` protocols; let SDK route methods. |
| Protocol version constant | yes | Use `acp.PROTOCOL_VERSION`. |
| Content block builders | yes | Use `text_block`, `resource_link_block`, `image_block`, etc. |
| Session update builders | yes | Use `update_agent_message`, `update_plan`, `start_tool_call`, `update_tool_call`. |
| ACP process spawning | yes | Use `spawn_agent_process` for reverse-direction ACP bridges. |
| Schema drift tracking | mostly yes | Pin/upgrade `agent-client-protocol`; do not vendor schema manually. |

This delegation removes a large class of low-level compatibility risk. It also
means current handcrafted ACP-like dictionaries should be treated as temporary
projections, not as the long-term protocol representation.

### Responsibilities py-agent-ctrl Should Keep

These are outside ACP SDK scope and remain core `py-agent-ctrl` work:

| Responsibility | Keep in py-agent-ctrl? | Reason |
| --- | --- | --- |
| CLI binary discovery | yes | ACP does not know provider executable names or install paths. |
| Provider argv/env construction | yes | Provider-specific flags, auth env, sandbox flags, and model options are not ACP concepts. |
| Provider stream parsing | yes | Claude/Codex/Gemini/OpenCode/Pi event formats are outside ACP. |
| Provider session continuation/resume mapping | yes | ACP has session lifecycle, but provider session IDs and resume mechanics are local bridge concerns. |
| Normalized cross-provider facade | yes | `AgentCtrl.claude_code().execute(...)` remains the library's primary value. |
| Provider-specific permission modes | yes | ACP can express permission prompts, but provider flags/policies still need bridge logic. |
| Result aggregation and parse diagnostics | yes | ACP streams protocol events; `py-agent-ctrl` still needs aggregate `AgentResponse`. |
| Live CLI smoke tests | yes | ACP SDK cannot verify native CLI behavior. |

In other words, ACP can replace protocol infrastructure, not the direct-agent
control abstraction.

### Shared Responsibilities Requiring an Adapter

Some concepts exist in both systems but do not line up one-to-one. These need
explicit mapping code:

| Concept | ACP side | py-agent-ctrl side | Adapter decision |
| --- | --- | --- | --- |
| Session | ACP session ID and lifecycle methods | provider session ID, execution ID, resume/continue flags | maintain a registry with both ACP and provider identifiers |
| Prompt | content block array | plain string prompt plus provider options | flatten or enrich text/resource blocks; reject or advertise unsupported media conservatively |
| Stream | async `Client.session_update` notifications | sync `StreamResult` iterator | bridge via async queue/thread or future async bridge API |
| Tool call | start/progress/update models with content variants | single `ToolCall` model with optional output/status | extend internal lifecycle or synthesize ACP lifecycle from completed events |
| Permission | `session/request_permission` request/response | local `PermissionBroker` and provider policy options | translate option kinds and cancellation semantics |
| Capabilities | ACP `AgentCapabilities`/`ClientCapabilities` | `BridgeCapabilities` and provider option support | derive ACP capabilities from configured bridge plus adapter policy |
| Cancellation | `session/cancel` -> `PromptResponse(cancelled)` | timeout/process termination currently | add cooperative cancellation hooks and permission cleanup |
| Filesystem | client methods with absolute paths | working directory/additional dirs | add guarded filesystem service only when ACP client role is needed |
| Terminal | client-managed terminal IDs | subprocess executor | add terminal service with lifecycle handles if driving ACP agents |

### Degree of Overlap

Approximate overlap by layer:

- **Protocol layer:** very high overlap. ACP SDK should own almost all of this.
- **Session/event vocabulary:** high overlap. ACP provides a richer target model,
  but `py-agent-ctrl` must map provider events into it.
- **Permission/cancellation semantics:** medium-high overlap. ACP gives the
  shape, while provider-specific enforcement stays local.
- **Filesystem/terminal service concepts:** medium overlap. ACP defines client
  callbacks; `py-agent-ctrl` has subprocess and cwd concepts but lacks the ACP
  service handles and guardrails.
- **Provider bridge implementation:** low overlap. ACP does not replace
  provider adapters.
- **User-facing Python facade:** low-medium overlap. ACP can add an
  interoperability surface, but it does not replace `AgentCtrl`.

The most useful mental model is: ACP is the **standard external protocol**;
`py-agent-ctrl` is the **provider bridge and normalized control library**.

### How Much Can Be Delegated Away?

Substantial infrastructure can be delegated away:

- all JSON-RPC transport mechanics;
- all generated ACP schema maintenance;
- all ACP method routing;
- most content/update model construction;
- ACP-compatible subprocess spawning for external ACP agents.

But the strategic responsibilities cannot be delegated:

- choosing and configuring which native CLI agent to run;
- translating ACP prompt/session requests into provider invocations;
- parsing provider-native streams back into normalized events;
- deciding what capabilities are honestly supported by each provider;
- enforcing local policy around cwd, additional directories, sandboxing,
  permissions, and terminal/filesystem access;
- preserving the existing direct Python API.

This means ACP should reduce implementation risk and surface area, but it should
not become the whole architecture. The correct design is an ACP adapter backed
by `py-agent-ctrl`, not a rewrite of `py-agent-ctrl` as a thin import of
`agent-client-protocol`.

### Add an ACP Agent Wrapper

Add a module such as:

```text
libs/py_agent_ctrl/adapters/acp/
  __init__.py
  agent.py
  client.py
  models.py
  projection.py
  sessions.py
  terminals.py
  filesystem.py
```

The first critical piece is `PyAgentCtrlAcpAgent(acp.Agent)`.

Responsibilities:

- implement `initialize` and return ACP capabilities derived from configured
  bridges;
- implement `new_session` and create an ACP session record;
- implement `prompt` by converting ACP prompt blocks into an `AgentRequest`;
- choose the underlying bridge for the session;
- stream bridge events as `Client.session_update(...)` notifications;
- return `PromptResponse(stop_reason=...)`;
- implement `cancel` by cancelling the underlying stream/process where
  supported;
- optionally implement list/resume/close if backed by provider session support.

The ACP SDK should own JSON-RPC and stdio:

```python
from acp import run_agent

async def main() -> None:
    await run_agent(PyAgentCtrlAcpAgent(...))
```

### Replace Dict Projection with SDK Models

Current `event_to_acp_update` should become a projection layer that returns ACP
model instances, not dictionaries.

Examples:

- `AgentTextEvent` -> `acp.update_agent_message(acp.text_block(...))`
- `AgentReasoningEvent` -> `acp.update_agent_thought(acp.text_block(...))`
- `AgentPlanUpdateEvent` -> `acp.update_plan([...])`
- `AgentToolCallEvent` -> `acp.start_tool_call(...)` or
  `acp.update_tool_call(...)`
- `AgentFileChangeEvent` -> tool call with `tool_diff_content(...)`
- terminal-backed command events -> tool call with `tool_terminal_ref(...)`

This avoids maintaining field aliases and discriminator values manually.

### Add an ACP Session Registry

ACP sessions need state that the current one-shot request model does not hold.

Suggested session record:

- ACP `session_id`;
- selected `AgentType`;
- selected bridge;
- `cwd`;
- `additional_directories`;
- `mcp_servers`;
- model/mode/config options;
- provider session ID, if known;
- active execution/stream handle;
- permission broker for the active turn;
- cancellation token/state.

The session registry is the boundary between ACP's multi-session connection and
`py-agent-ctrl`'s current one-request bridge API.

### Add Async Boundary Adapters

ACP SDK methods are async. Current `py-agent-ctrl` bridge APIs are synchronous.

The ACP wrapper should either:

- run blocking bridge execution in `asyncio.to_thread`; or
- introduce async bridge methods later and keep the ACP wrapper thin.

For first implementation, `asyncio.to_thread` is probably enough for
`execute()`. For streaming, use a thread/queue bridge so sync `StreamResult`
events can be forwarded through async `Client.session_update` without blocking
the event loop.

### Add Optional ACP Client Wrapper

If `py-agent-ctrl` should also be able to drive external ACP agents, add a
separate `AcpAgentBridge` that implements `AgentBridge` by launching an ACP
agent process with `acp.spawn_agent_process()`.

That bridge would let the normal API call an external ACP agent:

```python
AgentCtrl.acp(command=[...]).stream("...")
```

Required `acp.Client` callbacks:

- `session_update` -> convert ACP updates back into internal `AgentEvent`;
- `request_permission` -> use `PermissionBroker` or configured policy;
- `read_text_file` / `write_text_file` -> guarded filesystem service;
- `create_terminal` / `terminal_output` / `wait_for_terminal_exit` /
  `kill_terminal` / `release_terminal` -> guarded terminal service.

This is optional if the first goal is only to expose `py-agent-ctrl` as an ACP
agent.

## Detailed Gaps to Close

### 1. Dependency and Packaging

Current gap:

- no `agent-client-protocol` dependency.

Recommended fix:

- add an optional dependency group:

```toml
[project.optional-dependencies]
acp = [
    "agent-client-protocol>=0.12",
]
```

- keep core dependency-light behavior for users who only need direct CLI
  control;
- add an ACP CLI entrypoint only if needed, for example
  `ctrlagent-acp = "py_agent_ctrl.adapters.acp.cli:main"`.

### 2. Correct ACP Field Names and Validation

Current gap:

- adapter emits snake_case dicts that are not guaranteed ACP wire shape.

Recommended fix:

- return SDK model instances or SDK helper outputs;
- validate projection output with `model_validate`/`model_dump(by_alias=True)`
  where appropriate;
- keep tests close to ACP SDK models rather than current handcrafted dicts.

### 3. Agent Server Lifecycle

Current gap:

- no ACP server.

Recommended fix:

- implement `acp.Agent`;
- start with `initialize`, `new_session`, `prompt`, `cancel`, and
  `close_session`;
- use `acp.run_agent()` for stdio server mode;
- make bridge selection explicit through agent config or session config.

### 4. Prompt Block Conversion

Current gap:

- only plain string prompts are supported.

Recommended fix:

- convert ACP text blocks into prompt text;
- include resource links in the prompt or structured provider options;
- initially reject unsupported image/audio/embedded resources unless the bridge
  can support them;
- advertise prompt capabilities conservatively.

### 5. Streaming Semantics

Current gap:

- stream events are internal sync iterator events, not ACP notifications.

Recommended fix:

- forward each internal event through `Client.session_update`;
- preserve event order;
- do not include internal parser noise;
- return final `PromptResponse` only after stream exhaustion or cancellation;
- map subprocess timeout/failure into a sensible stop reason plus final visible
  warning/error update.

### 6. Tool Call Lifecycle

Current gap:

- tool calls are mostly one event with output already attached.

Recommended fix:

- extend internal `ToolCall`/events with lifecycle phase, kind, locations,
  content, raw input, raw output, and terminal reference support;
- map provider-specific starts/results separately where possible;
- for providers that only emit completed tool calls, emit a single completed
  `tool_call` or immediate `tool_call` plus `tool_call_update`;
- normalize statuses to ACP `pending`, `in_progress`, `completed`, or `failed`.

### 7. Permission Flow

Current gap:

- permission models and broker exist but are not an ACP callback path.

Recommended fix:

- remove or translate non-ACP `ABORT` option kind at the ACP boundary;
- implement `session/request_permission` in the ACP agent wrapper when provider
  events indicate approval is needed;
- resolve outstanding permission requests on `session/cancel`;
- decide whether provider-native permissions are controlled through CLI flags,
  callback injection, or policy-only behavior.

### 8. Filesystem and Terminal Services

Current gap:

- no ACP client callbacks for filesystem or terminal.

Recommended fix:

- for the ACP agent-server path, this is only needed if `py-agent-ctrl`-backed
  agents want to ask their host ACP client to read/write files or run terminals;
- for the ACP client-bridge path, it is required to drive external ACP agents;
- implement absolute-path enforcement, cwd/additional-directory guardrails, byte
  limits, stderr tail capture, terminal IDs, lifecycle cleanup, and release
  semantics.

### 9. Session Operations

Current gap:

- provider resume/continue exists in `AgentRequest`, and some bridge capability
  flags exist, but ACP session lifecycle is absent.

Recommended fix:

- implement ACP session IDs independently from provider session IDs;
- map ACP `session/resume` and `session/load` only when bridge support is real;
- advertise optional session capabilities based on configured bridge support;
- keep unsupported lifecycle methods absent or return protocol errors through
  SDK mechanisms.

### 10. Capabilities

Current gap:

- `BridgeCapabilities` is not ACP capability negotiation.

Recommended fix:

- create a mapper:
  `BridgeCapabilities` + adapter config -> `acp.schema.AgentCapabilities`;
- advertise only supported prompt/content/session/MCP capabilities;
- create conservative defaults, especially for image/audio/embedded context and
  terminal/filesystem behavior.

### 11. Tests and Verification

Current gap:

- tests only check dict projection.

Recommended fix:

- add model-level projection tests against ACP SDK classes;
- add loopback tests using the SDK's connection helpers;
- add a smoke test that launches `ctrlagent-acp` and drives it with an ACP
  client;
- keep existing direct bridge tests separate from ACP protocol tests;
- use one fake bridge fixture to avoid requiring live Claude/Codex/Gemini CLIs
  for ACP protocol tests.

## Suggested Implementation Sequence

This sequence keeps risk low and avoids replacing the existing library shape.

1. Add an optional `acp` extra with `agent-client-protocol`.
2. Convert `adapters/acp.py` projection from dicts to SDK model/helper outputs.
3. Add tests proving projected updates validate as ACP schema models.
4. Introduce an in-memory `AcpSessionRegistry`.
5. Implement `PyAgentCtrlAcpAgent.initialize()` and `.new_session()`.
6. Implement `.prompt()` over a fake bridge and stream updates through
   `Client.session_update`.
7. Add `.cancel()` semantics and process/stream cancellation hooks.
8. Add a `ctrlagent-acp` stdio entrypoint using `acp.run_agent()`.
9. Add real bridge smoke coverage for one provider, probably Codex or Claude
   Code, behind an opt-in marker.
10. Decide whether to implement the reverse direction:
    `AcpAgentBridge` for driving external ACP agents as normal `py-agent-ctrl`
    providers.

## Bottom Line

The current ACP adapter is useful as an early vocabulary experiment, but it is
not close to full ACP compliance.

Using `acp-python-sdk` changes the work from "implement a protocol" to "adapt
`py-agent-ctrl` semantics into the SDK's protocol interfaces." The largest
remaining gaps are not schema or transport. They are session state, prompt block
conversion, async streaming, cancellation semantics, capability negotiation, and
bridging provider-specific tool/permission behavior into ACP's structured event
model.
