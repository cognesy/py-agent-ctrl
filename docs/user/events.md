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
| `AgentTextEvent` | `text` | `text`, `raw` | Assistant-facing text output from the provider stream. |
| `AgentToolCallEvent` | `tool_call` | `tool_call`, `raw` | A provider reports tool use, command execution, MCP calls, search, file changes modeled as tools, or another structured action. |
| `AgentResultEvent` | `result` | `session_id`, `cost_usd`, `duration_ms`, `raw` | A provider emits final or session-level metadata. |
| `AgentReasoningEvent` | `reasoning` | `text`, `raw` | A provider exposes reasoning/thinking text separately from the final answer. |
| `AgentPlanUpdateEvent` | `plan_update` | `plan`, `raw` | A provider exposes a plan or plan update. The `plan` shape is provider-normalized only where possible. |
| `AgentUsageEvent` | `usage` | `usage`, `raw` | Token usage is available before or during final result reduction. |
| `AgentWarningEvent` | `warning` | `message`, `raw` | The bridge surfaces a recoverable warning or provider diagnostic. |
| `AgentFileChangeEvent` | `file_change` | `path`, `action`, `diff`, `raw` | A provider exposes file edit/change information in a form the bridge can normalize. |
| `AgentUnknownEvent` | `unknown` | `raw` | The provider emitted a valid payload that does not map to a known normalized event yet. |

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

