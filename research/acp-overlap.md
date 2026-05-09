# ACP and py-agent-ctrl Conceptual Overlap

Last updated: 2026-05-09

## Existing Overlap

- **Agent/client control boundary**
  - ACP defines how a client sends prompts to an agent and receives structured updates.
  - `py-agent-ctrl` already acts as a client/controller for CLI agents through `AgentBridge.execute()` and `AgentBridge.stream()`.

- **Prompt execution**
  - ACP has `session/prompt`.
  - `py-agent-ctrl` has `AgentRequest.prompt` plus bridge `execute()` / `stream()` methods.
  - Overlap: both model "send this user request to an agent and get work back."

- **Streaming output**
  - ACP streams `session/update` notifications.
  - `py-agent-ctrl` streams `AgentEvent` objects through `StreamResult`.
  - Overlap: both expose incremental agent progress instead of only final text.

- **Agent message chunks**
  - ACP has `agent_message_chunk`.
  - `py-agent-ctrl` has `AgentTextEvent`.
  - This is a near-direct conceptual match.

- **Reasoning/thought events**
  - ACP has `agent_thought_chunk`.
  - `py-agent-ctrl` has `AgentReasoningEvent`.
  - This overlaps, though ACP has a formal protocol shape and `py-agent-ctrl` keeps it as internal normalized event data.

- **Tool calls**
  - ACP has structured `tool_call` and `tool_call_update`.
  - `py-agent-ctrl` has `ToolCall` and `AgentToolCallEvent`.
  - Overlap: both track tool name, ID, input, output, status/error.
  - Gap: ACP models lifecycle and display content more fully.

- **Plan updates**
  - ACP has `plan` session updates.
  - `py-agent-ctrl` has `AgentPlanUpdateEvent`.
  - Overlap: both can represent an agent's execution plan.

- **Usage/cost reporting**
  - ACP has `usage` updates and prompt response usage.
  - `py-agent-ctrl` has `TokenUsage`, `AgentUsageEvent`, `AgentResponse.usage`, and `cost_usd`.
  - Overlap: both expose token/accounting metadata.

- **Session identity**
  - ACP has protocol sessions with `session/new`, `session/load`, `session/resume`, etc.
  - `py-agent-ctrl` has `session_id`, `resume_session_id`, and `continue_session`.
  - Overlap: both need to maintain conversation continuity.
  - Gap: `py-agent-ctrl` currently maps provider sessions, not ACP sessions.

- **Capabilities**
  - ACP has negotiated `AgentCapabilities` and `ClientCapabilities`.
  - `py-agent-ctrl` has `BridgeCapabilities`.
  - Overlap: both describe what an agent/backend can do.
  - Gap: ACP capabilities are protocol-level; `py-agent-ctrl` capabilities are provider/bridge-level.

- **Permissions**
  - ACP has `session/request_permission`.
  - `py-agent-ctrl` has `PermissionRequest`, `PermissionResponse`, `PermissionOption`, and `PermissionBroker`.
  - Overlap: both model approval flows for sensitive tool actions.
  - Gap: `py-agent-ctrl` has the data shape, but it is not wired into ACP request/response traffic.

- **Filesystem access**
  - ACP defines `fs/read_text_file` and `fs/write_text_file`.
  - `py-agent-ctrl` has `working_directory` and `additional_directories`.
  - Overlap: both care about controlled workspace access.
  - Gap: `py-agent-ctrl` does not yet expose ACP filesystem callbacks.

- **Terminal/subprocess execution**
  - ACP defines `terminal/create`, `terminal/output`, `terminal/wait_for_exit`, `terminal/kill`, and `terminal/release`.
  - `py-agent-ctrl` has `HostCommandExecutor`, subprocess execution, streaming lines, timeout handling, stderr tail capture.
  - Overlap: both manage command execution.
  - Gap: ACP terminal API is client-facing with terminal IDs; `py-agent-ctrl` subprocess execution is internal bridge infrastructure.

- **Cancellation/timeouts**
  - ACP has `session/cancel` and `stopReason="cancelled"`.
  - `py-agent-ctrl` has process timeouts and subprocess kill behavior.
  - Overlap: both need to stop in-flight work.
  - Gap: ACP cancellation is semantic and protocol-visible; `py-agent-ctrl` currently treats it more as process control.

## What py-agent-ctrl Duplicates From ACP

- It defines its own normalized event vocabulary where ACP already has `SessionUpdate`.
- It defines tool-call models where ACP already has `ToolCall`, `ToolCallUpdate`, tool content, locations, raw input, and raw output.
- It defines permission request/response models where ACP already has `RequestPermissionRequest` and `RequestPermissionResponse`.
- It defines capability models where ACP already has `AgentCapabilities` and `ClientCapabilities`.
- It has an ACP-shaped adapter that manually emits dictionaries where the ACP SDK already provides generated models and helper builders.
- It has subprocess/streaming primitives that partially overlap with ACP terminal concepts, though the use case differs.
- It has session continuation fields that overlap conceptually with ACP session lifecycle, but are provider-session oriented rather than protocol-session oriented.

## Key Distinction

`py-agent-ctrl` duplicates some **protocol vocabulary**, but it does not
duplicate ACP's actual **protocol implementation** yet.

The duplicated protocol-shaped parts should mostly become mappings to
`acp-python-sdk` models. `py-agent-ctrl` should keep the provider-specific bridge
logic: CLI discovery, argv/env construction, provider stream parsing, provider
session mapping, and the direct `AgentCtrl` facade.

