# Problems We May Have Missed

These are problem areas surfaced by the alternatives that are not fully handled
in `py-agent-ctrl` yet.

## Process Lifecycle

- Graceful shutdown needs multiple phases: close stdin, drain stdout/stderr,
  terminate, then kill.
- Streaming parsers should start before subprocess start to avoid missing output
  from short-lived commands.
- `stderr` should be tailed and included in normalized failures, not only
  discarded or returned as a raw blob.
- Some provider CLIs emit useful JSON before exiting non-zero; parsed output
  should be preserved in failure responses when available.
- Large or partial JSON messages need buffering with max-size protection.
- Some stdout lines are non-JSON diagnostics; parsers need a policy to skip or
  record them without corrupting the stream.

## Security And Isolation

- Sandbox driver fields are not enough. We need an executor policy that defines
  environment inheritance, network policy, writable paths, extra readable paths,
  temp directories, and command timeout.
- Prompt-file and file-access APIs need path validation and symlink handling.
- Nested agent launches can inherit dangerous or confusing env vars such as
  `CLAUDECODE`; provider-specific env cleanup is required.
- API keys and tokens need masking in logs and callback diagnostics.
- Worktree isolation may be more practical than heavy sandboxing for many coding
  tasks and should be considered separately.

## Permissions

- The current callback/wiretap model observes tool calls but does not manage
  permission requests.
- Permission state needs IDs, option kinds, pending request storage, response
  mapping, auto-approval policy, denial, abort, and cancellation cleanup.
- "Approve once" and "approve for session" are different outcomes and should not
  collapse into one boolean.
- Cancellation should resolve pending permissions with a cancelled outcome.

## Event Model

- Text and final result are not enough. The alternatives model thought/reasoning,
  plan updates, token counts, rate limits, tool start/progress/result, file
  diffs, terminal output references, current mode, available commands, and usage
  updates.
- Some providers stream cumulative text, not deltas. We need deduplication logic
  to avoid repeated text in callbacks.
- Some providers leak internal JSON as text. We need suppression/normalization
  hooks for known provider control messages.
- Stale events can arrive from older turns or sessions. Event projectors should
  carry and check session/turn IDs where providers expose them.

## Session Semantics

- Provider session ID and `py-agent-ctrl` execution ID must stay distinct.
- Some session IDs are discoverable only via transcript/storage scanning, not
  stdout.
- Resuming, continuing, forking, tagging, renaming, and deleting sessions are
  separate operations in mature SDKs.
- Session history reconstruction can require following parent UUID chains and
  filtering sidechains/meta/compact-summary/progress messages.

## Configuration

- Agent presets are more than model aliases: they can define backend, model,
  prompt file, reasoning effort, base URL/API key, tool allow/deny lists, and
  yolo/permission mode.
- Provider-native options should stay provider-specific. A single common option
  bag will either be too weak or misleading.
- Environment defaults should be explicit and minimal. ACP's trimmed environment
  is a useful model for subprocess safety.

## Observability

- Logs need execution ID, provider session ID, backend, argv preview, cwd, PID,
  start/end times, exit code, timeout/cancellation reason, parse failures, and
  stderr tail.
- Structured output should include enough information for orchestrators:
  message, session ID, exit code, error, files changed, tests, coverage, log
  path, and raw response.
- Error taxonomy should separate binary-not-found, working-directory-not-found,
  process failure, timeout, cancellation, JSON decode failure, and provider parse
  failure.

## Protocol Boundaries

- ACP suggests a richer public protocol, but it should remain an adapter target
  until target CLIs converge on ACP.
- If we support ACP later, every path crossing that boundary should be absolute.
- Terminal delegation is a different abstraction from direct subprocess
  execution. We should not mix them accidentally.

## Orchestration

- Multi-agent parallel execution needs dependency graphs, bounded concurrency,
  cancellation propagation, per-task logs, and failure-based skip behavior.
- That belongs above the bridge layer. Individual provider bridges should remain
  single-request/session primitives.

## Immediate Design Implications

- Keep the new `SandboxDriver` API, but implement it behind a real
  `CommandExecutor` abstraction before relying on it.
- Add shared JSONL buffering and process execution primitives before adding more
  provider features.
- Expand `AgentEvent` carefully, preserving backward compatibility with existing
  `AgentTextEvent`, `AgentToolCallEvent`, and `AgentResultEvent`.
- Add provider-specific option models or typed helpers incrementally, starting
  with the options users actually need from xqa.
