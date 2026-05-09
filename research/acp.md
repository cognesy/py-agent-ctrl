# ACP Cheatsheet: Agent Client Protocol

Last updated: 2026-05-09

> Naming note: the local SDK and official documentation use **ACP** for
> **Agent Client Protocol**, not "Agent Control Protocol". There are other
> projects and papers using the same acronym for different protocols. This note
> describes the protocol implemented by `agent-client-protocol` and the local
> Python SDK checkout.

## Sources

- Official protocol docs: <https://agentclientprotocol.com/protocol/overview>
- Official architecture docs: <https://agentclientprotocol.com/get-started/architecture>
- Official transport docs: <https://agentclientprotocol.com/protocol/transports>
- Official schema docs: <https://agentclientprotocol.com/protocol/schema>
- Local SDK repo: `/Users/ddebowczyk/projects/_ext/acp-python-sdk`
- Local SDK schema snapshot: `schema/VERSION` = `refs/tags/v0.12.2`
- Local SDK protocol major: `src/acp/meta.py` = `PROTOCOL_VERSION = 1`

## One-line Definition

Agent Client Protocol is a JSON-RPC protocol for connecting user-facing clients
such as editors, terminals, notebooks, and custom UIs to AI coding agents. The
client owns the user interface and local environment; the agent owns reasoning,
tool planning, and execution orchestration.

## What Problem It Solves

ACP standardizes the boundary between "an app the user is operating" and "an
agent that can act on code":

- clients can embed many agents without bespoke process protocols for each one;
- agents can run in many clients without building a custom editor integration;
- streamed agent output, plans, tool calls, permissions, terminals, and session
state have a shared vocabulary;
- capabilities are negotiated so clients and agents can degrade gracefully.

It is best understood as an **agent-to-client runtime protocol**, not as a
general multi-agent coordination protocol and not as a replacement for MCP.

## Core Roles

| Role | Owns | Typical examples |
| --- | --- | --- |
| Client | UI, workspace access, permission UX, local terminals, user-facing session state | Zed, editor plugin, notebook kernel, terminal UI, `py-agent-ctrl` adapter |
| Agent | LLM loop, tool planning, tool execution, model/provider integrations, response streaming | coding-agent CLI, ACP subprocess, Gemini bridge, Kimi CLI style agent |

The architecture assumes the client often launches the agent as a subprocess on
demand. A single connection can support multiple sessions.

## Transport

ACP uses JSON-RPC 2.0 messages.

The primary transport today is **stdio**:

- client launches agent as a subprocess;
- client writes JSON-RPC messages to the agent's `stdin`;
- agent writes JSON-RPC messages to `stdout`;
- each message is UTF-8 JSON delimited by a newline;
- `stdout` must contain only valid ACP messages;
- agent logs belong on `stderr`.

The protocol is transport-agnostic at the message layer. Streamable HTTP is
documented as a draft/in-progress transport, and custom transports are allowed
if they preserve JSON-RPC semantics and ACP lifecycle requirements.

## Minimal Lifecycle

```text
Client -> Agent: initialize
Agent  -> Client: initialize result with selected protocol version/capabilities

Client -> Agent: authenticate, if required

Client -> Agent: session/new
Agent  -> Client: session id

Client -> Agent: session/prompt
Agent  -> Client: session/update notifications while working
Agent  -> Client: session/request_permission, fs/*, terminal/* as needed
Client -> Agent: session/cancel notification, if user interrupts
Agent  -> Client: final session/prompt response with stopReason
```

Baseline agent support:

- `initialize`
- `session/new`
- `session/prompt`
- `session/cancel`
- `session/update`

## Message Shape

ACP uses JSON-RPC methods for request/response traffic and notifications for
one-way events.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "session/prompt",
  "params": {
    "sessionId": "sess_123",
    "prompt": [
      { "type": "text", "text": "Review this repository." }
    ]
  }
}
```

Notifications omit `id` and do not receive responses:

```json
{
  "jsonrpc": "2.0",
  "method": "session/update",
  "params": {
    "sessionId": "sess_123",
    "update": {
      "sessionUpdate": "agent_message_chunk",
      "content": { "type": "text", "text": "I will inspect the tests first." }
    }
  }
}
```

## Initialization and Capabilities

`initialize` negotiates:

- protocol major version;
- client capabilities;
- agent capabilities;
- optional implementation metadata;
- optional authentication methods.

The client sends the latest protocol version it supports. The agent returns the
chosen version. If the client cannot support the agent's chosen version, the
client should close the connection and tell the user.

Capabilities are additive and optional. Omitted capabilities must be treated as
unsupported.

Common client capabilities:

- `fs.readTextFile`
- `fs.writeTextFile`
- `terminal`
- unstable auth, elicitation, NES, and position encoding fields

Common agent capabilities:

- `loadSession`
- `promptCapabilities.image`
- `promptCapabilities.audio`
- `promptCapabilities.embeddedContext`
- `mcpCapabilities.http`
- `mcpCapabilities.sse`
- session list/resume/close/fork support
- unstable provider, auth, and NES fields

## Directional Method Map

Client calls the agent:

| Method | Purpose | Baseline? |
| --- | --- | --- |
| `initialize` | Version and capability negotiation | yes |
| `authenticate` | Run an agent-advertised auth method | conditional |
| `session/new` | Create a new conversation session | yes |
| `session/prompt` | Send a user message into a session | yes |
| `session/cancel` | Cancel the active prompt turn | yes, notification |
| `session/load` | Load an existing session | optional |
| `session/list` | List known sessions | optional |
| `session/resume` | Resume an existing session | optional |
| `session/close` | Close a session | optional |
| `session/fork` | Fork a session | unstable/optional |
| `session/set_mode` | Change agent operating mode | optional |
| `session/set_config_option` | Change a session config option | optional |
| `session/set_model` | Change model for the session | unstable/optional |
| `document/didOpen`, `didChange`, `didSave`, `didClose`, `didFocus` | Editor document notifications | unstable/optional |
| `nes/*` | Next Edit Suggestion lifecycle | unstable/optional |
| `providers/*`, `logout` | Provider configuration/auth management | unstable/optional |

Agent calls the client:

| Method | Purpose | Requires capability? |
| --- | --- | --- |
| `session/update` | Stream progress, output, plan, tool calls, state | baseline notification |
| `session/request_permission` | Ask user/client to approve a tool call | baseline client method |
| `fs/read_text_file` | Read a text file from the client's filesystem | `fs.readTextFile` |
| `fs/write_text_file` | Write text to a client-side file | `fs.writeTextFile` |
| `terminal/create` | Start a command in a client-managed terminal | `terminal` |
| `terminal/output` | Read terminal output/status | `terminal` |
| `terminal/wait_for_exit` | Wait for command completion | `terminal` |
| `terminal/kill` | Kill a command without releasing terminal handle | `terminal` |
| `terminal/release` | Release terminal resources | `terminal` |
| `elicitation/create` | Request structured user input | unstable/optional |
| `elicitation/complete` | Signal URL elicitation completion | unstable/optional notification |

## Prompt Turn

A prompt turn is one full user-agent interaction:

1. Client sends `session/prompt` with content blocks.
2. Agent processes the prompt and may call an LLM repeatedly.
3. Agent streams `session/update` notifications for messages, thoughts, plans,
   tool-call starts, tool-call progress, usage, modes, and session info.
4. Agent may request client permissions or client resources during execution.
5. Agent returns the original `session/prompt` response with a `stopReason`.

Stop reasons include:

- `end_turn`
- `max_tokens`
- `max_turn_requests`
- `refusal`
- `cancelled`

Cancellation is semantic, not just transport failure. If the client sends
`session/cancel`, the agent should stop LLM calls and tool execution promptly,
send any final updates, and then complete the pending `session/prompt` response
with `stopReason = "cancelled"`. Pending permission requests must be resolved
with the cancelled outcome.

## Content Blocks

ACP reuses MCP-like content blocks so agent/client integrations can pass
structured user-facing content without inventing new wrappers.

| Block | Use | Prompt support |
| --- | --- | --- |
| `text` | Plain text | required |
| `resource_link` | Reference to external/file/resource context | required baseline |
| `resource` | Embedded text/blob resource | requires `embeddedContext` |
| `image` | Base64 image with MIME type | requires `image` |
| `audio` | Base64 audio with MIME type | requires `audio` |

Clients must restrict prompt content according to the agent's advertised
`promptCapabilities`.

## Session Updates

`session/update` is the main streaming channel from agent to client. In the
local SDK schema, `SessionUpdate` is a discriminated union using
`sessionUpdate`.

Important variants:

- `user_message_chunk`
- `agent_message_chunk`
- `agent_thought_chunk`
- `tool_call`
- `tool_call_update`
- `plan`
- `available_commands_update`
- `current_mode_update`
- `config_option`
- `session_info`
- `usage`

This is richer than a single stdout text stream. It gives clients enough data to
render message text, chain-of-action progress, tool status, plans, modes, and
cost/usage separately.

## Tool Calls

Tool calls are reported through `session/update`, not hidden in raw text.

Typical lifecycle:

```text
Agent -> Client: session/update { sessionUpdate: "tool_call", toolCallId, title, kind, status: "pending" }
Agent -> Client: session/request_permission, if needed
Client -> Agent: permission result
Agent -> Client: session/update { sessionUpdate: "tool_call_update", status: "in_progress" }
Agent -> Client: session/update { sessionUpdate: "tool_call_update", status: "completed", content: [...] }
```

Tool kinds are presentation hints for clients. The docs/schema include kinds
such as:

- `read`
- `edit`
- `delete`
- `move`
- `search`
- `execute`
- `think`
- `fetch`
- `switch_mode`
- `other`

Tool call records can carry:

- human title;
- execution status;
- produced content;
- affected locations;
- raw input;
- raw output;
- terminal references;
- diff/file-edit content.

## Permissions

Agents may ask the client to authorize a tool call with
`session/request_permission`.

Request fields:

- `sessionId`
- `toolCall`
- `options`

Permission options include:

- `optionId`
- display `name`
- `kind`: `allow_once`, `allow_always`, `reject_once`, or `reject_always`

The response is either:

- selected option: `{ "outcome": "selected", "optionId": "..." }`
- cancellation: `{ "outcome": "cancelled" }`

Clients may auto-allow or auto-reject according to user settings.

## Filesystem and Terminals

ACP deliberately lets the client expose local resources as capabilities instead
of assuming the agent process has direct unrestricted access.

Filesystem:

- `fs/read_text_file`
- `fs/write_text_file`
- paths are expected to be absolute;
- line numbers are 1-based.

Terminals:

- `terminal/create`
- `terminal/output`
- `terminal/wait_for_exit`
- `terminal/kill`
- `terminal/release`

The terminal API lets the client own command execution UX while the agent
receives terminal IDs and can embed terminal references in tool-call updates.

## MCP Relationship

ACP and MCP solve different boundaries:

- MCP connects an agent or host to tools/resources.
- ACP connects a client UI/runtime to an agent.

ACP is MCP-friendly:

- it reuses MCP-style content blocks;
- clients can pass MCP server configuration to agents during session setup;
- agents can connect directly to those MCP servers;
- a client can expose its own MCP server if it wants to provide tools without
  mixing MCP and ACP on the same socket.

## Extensibility

ACP has three intended extension points:

- `_meta` fields for custom metadata;
- custom methods prefixed with `_`;
- custom capabilities advertised during initialization.

The schema says implementations must not assume semantics for arbitrary `_meta`
keys. Use capabilities for negotiated behavior, not silent assumptions.

## Python SDK Mapping

The local Python SDK is a concrete implementation helper, not the protocol
itself.

Key modules:

- `acp.schema` - generated Pydantic models from the upstream JSON schema.
- `acp.interfaces.Agent` - protocol methods an agent implements.
- `acp.interfaces.Client` - callbacks/methods a client implements.
- `acp.agent` / `acp.client` - async connection/router helpers.
- `acp.stdio` / `acp.transports` - stdio process plumbing.
- `acp.helpers` - builders for text blocks, resource blocks, tool calls, plan
  updates, and session notifications.
- `acp.contrib.session_state` - session update accumulation utilities.
- `acp.contrib.tool_calls` - tool-call lifecycle helpers.
- `acp.contrib.permissions` - permission broker patterns.

Minimal agent pattern from the repo:

```python
from acp import Agent, InitializeResponse, NewSessionResponse, PromptResponse


class MyAgent(Agent):
    async def initialize(self, protocol_version, client_capabilities=None, client_info=None, **kwargs):
        return InitializeResponse(protocol_version=protocol_version)

    async def new_session(self, cwd, additional_directories=None, mcp_servers=None, **kwargs):
        return NewSessionResponse(session_id="sess_123")

    async def prompt(self, prompt, session_id, message_id=None, **kwargs):
        # stream updates via self._conn.session_update(...)
        return PromptResponse(stop_reason="end_turn", user_message_id=message_id)
```

Client-side programmatic launch uses `spawn_agent_process(...)` and then calls:

```python
await conn.initialize(protocol_version=PROTOCOL_VERSION)
session = await conn.new_session(cwd="/abs/project", mcp_servers=[])
await conn.prompt(session_id=session.session_id, prompt=[text_block("Hello")])
```

## Relevance to `py-agent-ctrl`

`py-agent-ctrl` should not blindly become an ACP runtime. The repo's current
goal is a direct Python abstraction over existing CLI agents such as Claude
Code, Codex, OpenCode, Pi, and Gemini. Most of those CLIs emit provider-native
JSONL, stdout, or TUI/transcript formats, not ACP.

Useful ACP ideas to borrow:

- normalized event vocabulary beyond plain output text;
- capability model for filesystem, terminal, permissions, streaming, sessions,
  and prompt content;
- explicit tool-call lifecycle with status updates and raw input/output;
- permission broker tied to a normalized tool call;
- semantic cancellation that drains final updates and resolves permissions;
- absolute path discipline for protocol-facing file operations;
- optional projection layer from internal events to ACP-like session updates.

Likely integration strategy:

1. Keep `py-agent-ctrl` core as a direct subprocess library.
2. Normalize provider events into internal Pydantic models.
3. Add an ACP projection/adapter later for clients that want ACP-compatible
   session updates.
4. Avoid adding the official ACP SDK as a hard runtime dependency until
   interoperability with actual ACP clients is required.

## Implementation Checklist for an ACP Adapter

- Define client and agent capability structs.
- Model content blocks explicitly, at least `text` and `resource_link`.
- Use session IDs and turn/message IDs consistently.
- Stream updates as structured events, not only text chunks.
- Track tool calls by stable `toolCallId`.
- Resolve permissions on cancellation.
- Keep protocol-facing file paths absolute.
- Preserve raw provider events for debugging.
- Treat unstable schema fields as optional integration experiments, not core
  contracts.
- Validate emitted payloads against the generated schema when practical.
