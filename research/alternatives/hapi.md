# HAPI

Local reference:
`/Users/ddebowczyk/projects/_ext/hapi`

## Fit

HAPI is a product, not a library abstraction. It wraps local CLI agents and
connects them to a hub/web/mobile control surface. The hub/server layer is not a
fit for `py-agent-ctrl`, but the local launcher and event normalization code
surface several problems a direct bridge can miss.

## Relevant Design

Common backend shape:

- `cli/src/agent/types.ts` defines an `AgentBackend` interface with
  `initialize`, `newSession`, `prompt`, `cancelPrompt`, permission response
  handling, and disconnect.
- `cli/src/agent/AgentRegistry.ts` registers backend factories by agent type.

Launch/session lifecycle:

- `cli/src/claude/claudeLocalLauncher.ts`,
  `cli/src/codex/codexLocalLauncher.ts`,
  `cli/src/gemini/geminiLocalLauncher.ts`, and
  `cli/src/opencode/opencodeLocalLauncher.ts` wrap provider-specific launch
  logic in a common local-launcher shape.
- `cli/src/agent/sessionBase.ts` tracks session ID, local/remote mode, runtime
  metadata, keepalive state, and callbacks for newly discovered session IDs.
- Codex, Gemini, Claude, and OpenCode have session scanners that read provider
  transcript/storage files to recover session IDs and stream history outside
  stdout.

ACP adapter:

- `cli/src/agent/backends/acp/AcpSdkBackend.ts` implements the `AgentBackend`
  shape over ACP stdio JSON-RPC.
- It waits for recent session updates to go quiet before starting a prompt and
  after a prompt returns, then flushes buffered text. This prevents late updates
  from leaking into the next prompt or being dropped.
- It rejects updates for a different active session ID.
- It tracks pending permission requests and maps user decisions back to ACP
  permission outcomes.

Event normalization:

- `cli/src/agent/backends/acp/AcpMessageHandler.ts` converts ACP session updates
  into app-level text/tool/plan events.
- It deduplicates cumulative text chunks with prefix/suffix/overlap checks.
- It suppresses internal event JSON and converts rate-limit JSON into a
  normalized user-facing message.
- It tracks tool call state across `tool_call` and `tool_call_update`.

Codex event handling:

- `cli/src/codex/utils/codexEventConverter.ts` handles a session-log event shape
  with `session_meta`, `event_msg`, `response_item`, reasoning deltas, token
  counts, and function-call outputs.
- `cli/src/codex/utils/appServerEventConverter.ts` handles a richer app-server
  notification model, including thread/turn events, diffs, reasoning deltas,
  command output deltas, and noisy events to ignore.
- `cli/src/codex/utils/terminalEventGuard.ts` ignores terminal events from stale
  turn IDs or anonymous events while a turn is in flight.

Permissions and path safety:

- `cli/src/agent/permissionAdapter.ts` maintains pending permission requests,
  auto-approval decisions, "approve once" vs "approve for session", denial, and
  abort handling.
- `cli/src/modules/common/pathSecurity.ts` validates paths against a working
  directory and handles case-insensitive Windows paths.

Error classification:

- `cli/src/agent/backends/acp/AcpStdioTransport.ts` classifies stderr into rate
  limit, model-not-found, authentication, quota-exceeded, and unknown errors.
- `cli/src/agent/rateLimitParser.ts` recognizes Claude rate-limit JSON leaked
  as text and suppresses or normalizes it.

## What To Borrow

- Add a richer stream event model over time: plan updates, reasoning, tool call
  start/update/result, usage/token-count updates, rate-limit events, and
  terminal/diff/file-change events.
- Track provider session ID separately from execution ID and reject stale events
  from other sessions/turns when possible.
- Add a permission abstraction before adding remote approval features: pending
  request store, response mapping, cancellation behavior, auto-approval policy.
- Add event text deduplication for cumulative providers.
- Add explicit internal-event suppression for provider JSON that should not be
  exposed as assistant text.
- Add provider-specific stderr classification beyond raw `stderr` strings.
- Add path validation helper for any future file-read/write or prompt-file API.

## What Not To Copy Directly

- The hub, Socket.IO, SSE, PWA, Telegram, and remote mode are outside the
  `py-agent-ctrl` library boundary.
- The local/remote handoff model adds product complexity we should avoid unless
  `py-agent-ctrl` becomes a session daemon.
- HAPI is AGPL-3.0, so this is design reference only.

## Gaps Relative To py-agent-ctrl

`py-agent-ctrl` currently normalizes a completed response and simple stream
events. It does not yet model permissions, plans, cumulative text deduplication,
turn IDs, rate limits, stale-event filtering, provider transcript scanning, or
long-running response drains.
