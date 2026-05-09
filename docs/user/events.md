# Stream Events

`py-agent-ctrl` streams normalized Pydantic event objects from provider-native
CLI output. The `type` field is the stable discriminator for each event variant.
Use `isinstance(...)` when working in Python, and use `event.type` when
serializing or logging events.

The normalized fields documented here are the stable API. The `raw` field, when
present, preserves the provider-native payload for debugging and advanced
integrations. Treat `raw` as provider-specific: it may differ between agents and
provider CLI versions.

## Consuming Events

```python
from py_agent_ctrl import AgentCtrl, AgentTextEvent, AgentToolCallEvent

result = AgentCtrl.codex().stream("Review the tests.")

for event in result:
    if isinstance(event, AgentTextEvent):
        print(event.text, end="", flush=True)
    elif isinstance(event, AgentToolCallEvent):
        print(f"\n[tool: {event.tool_call.name}]")

print(f"\nexit code: {result.exit_code}")
```

## Event Variants

| Event | `type` | Stable fields | When emitted |
| --- | --- | --- | --- |
| `AgentTextEvent` | `text` | `text`, `content`, `raw` | Assistant-facing text output from the provider stream. |
| `AgentToolCallEvent` | `tool_call` | `tool_call`, `phase`, `raw` | A provider reports tool use, command execution, MCP calls, search, file changes modeled as tools, or another structured action. |
| `AgentResultEvent` | `result` | `session_id`, `cost_usd`, `duration_ms`, `raw` | A provider emits final or session-level metadata. |
| `AgentReasoningEvent` | `reasoning` | `text`, `raw` | A provider exposes reasoning/thinking text separately from the final answer. |
| `AgentPlanUpdateEvent` | `plan_update` | `plan`, `raw` | A provider exposes a plan or plan update. The `plan` shape is provider-normalized only where possible. |
| `AgentUsageEvent` | `usage` | `usage`, `raw` | Token usage is available before or during final result reduction. |
| `AgentWarningEvent` | `warning` | `message`, `raw` | The bridge surfaces a recoverable warning or provider diagnostic. |
| `AgentFileChangeEvent` | `file_change` | `path`, `action`, `diff`, `raw` | A provider exposes file edit/change information in a form the bridge can normalize. |
| `AgentUnknownEvent` | `unknown` | `raw` | The provider emitted a valid payload that does not map to a known normalized event yet. |

## Tool-call Lifecycle

`AgentToolCallEvent.tool_call` is a `ToolCall` model. It describes the normalized
tool snapshot: stable-ish provider ID when available, normalized name and kind,
arguments, output, optional content blocks, error flag, status, lifecycle phase,
and raw provider data.

`ToolCall.status` describes the provider outcome when it can be normalized:

- `pending`
- `in_progress`
- `completed`
- `failed`
- `cancelled`

`ToolCall.phase` and `AgentToolCallEvent.phase` describe where the event sits in
the lifecycle:

- `started` means the provider exposed the beginning of a tool call.
- `updated` means the provider exposed an in-progress update.
- `completed`, `failed`, and `cancelled` mean the provider exposed or implied a
  terminal state.
- `snapshot` means the provider emitted a tool-like record whose status is
  missing or provider-specific, so `py-agent-ctrl` preserves it without claiming
  a terminal outcome.

Provider support differs. Claude Code exposes a pending tool-use event, so its
phase can be `started`. Gemini exposes `tool_use` and `tool_result`; aggregate
responses track both internally, while live streams still emit one visible
`tool_call` event when the result is paired. Codex, OpenCode, and Pi mostly
expose final snapshots, so their phase is inferred from the normalized status.

The lifecycle fields are additive. Existing `on_tool_call` callbacks still
receive `ToolCall` snapshots and are not called more often unless a provider
bridge deliberately emits more user-visible tool events in a future API change.

## Structured Content Blocks

`AgentRequest`, `AgentTextEvent`, `AgentResponse`, and `ToolCall` can carry
structured content blocks while preserving the existing string fields:

- `TextContentBlock`
- `ResourceLinkContentBlock`
- `EmbeddedResourceContentBlock`
- `ImageContentBlock`
- `DiffContentBlock`
- `TerminalContentBlock`

`AgentRequest.prompt`, `AgentTextEvent.text`, and `AgentResponse.text` remain
the convenience plain-text views. When request content is present, provider
command builders use deterministic fallback text. For example, a resource link
is rendered as `[resource: README.md] file:///tmp/README.md`.

Provider-native support is limited and explicit. Codex image references are
passed to the CLI as `--image` in addition to the fallback prompt text. Embedded
image data is not inlined into argv. Providers without native support still
receive the fallback text, so content is visible rather than silently discarded.

## Stable Versus Provider-specific Data

Stable:

- event class names;
- event `type` discriminator values;
- documented normalized fields;
- `ToolCall`, `TokenUsage`, and response models imported from `py_agent_ctrl`.

Provider-specific:

- `raw` payload shape;
- exact event ordering when a provider emits partial or delayed metadata;
- which optional event variants a provider can emit;
- text chunk granularity;
- provider-native tool names and provider-native status strings.

## Provider Differences

Not every CLI exposes the same stream structure. Some providers emit only text
and final metadata. Others expose command execution, tool use, file changes,
plans, reasoning, or usage. Callers should handle `AgentUnknownEvent` and should
not assume every bridge emits every event type.

Use `AgentCtrl.<provider>().capabilities()` to inspect bridge-level support
where available, and keep fallback behavior for missing optional events.
