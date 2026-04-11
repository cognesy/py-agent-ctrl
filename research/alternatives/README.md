# CLI Agent Abstraction Alternatives

This directory records design findings from local reference repos cloned under
`/Users/ddebowczyk/projects/_ext`.

The target problem is narrower than "agent framework": `py-agent-ctrl` should be
an in-process Python abstraction over existing CLI coding agents. It should not
require a long-running HTTP command surface.

## References Reviewed

- `myclaude/codeagent-wrapper`: direct multi-backend CLI wrapper in Go.
- `hapi`: local/remote control app with useful direct launcher, session, ACP,
  permission, and event-normalization internals.
- `agent-client-protocol` and `agent-client-protocol-python-sdk`: standards-track
  protocol and Python helpers for client-agent communication.
- `claude-agent-sdk-python`: official Claude-only subprocess SDK with a mature
  typed option surface and control protocol.

`coder/agentapi` was intentionally not analyzed here because its HTTP server
model is a poor fit for this project requirement.

## Main Conclusions

1. `py-agent-ctrl` is still justified as a direct Python library. None of the
   reviewed projects is a drop-in Python abstraction over Claude Code, Codex,
   OpenCode, Pi, and Gemini with normalized response DTOs.
2. The most transferable design is from `myclaude/codeagent-wrapper`: a small
   backend contract, provider-specific argv/env builders, stdin heuristics,
   process lifecycle hardening, stderr filtering, worktree isolation, and
   dependency-aware parallel execution.
3. HAPI is product-shaped, but it highlights problems a direct library can still
   miss: permission request lifecycle, stale event filtering, transcript/session
   scanning, rate limit normalization, internal event suppression, and
   "quiet-period" draining before declaring a stream complete.
4. ACP is the best candidate for a future protocol-facing surface. Its model is
   richer than our current `AgentEvent` union: content blocks, plan updates,
   tool-call start/progress/results, usage, modes, available commands, terminal
   delegation, permission requests, cancellation semantics, and capabilities.
5. The Claude SDK shows what provider-native depth looks like: wide typed option
   coverage, hooks, permission callbacks, stderr callbacks, bundled binary
   fallback, version checks, session metadata operations, and defensive subprocess
   shutdown.

## Recommended Direction

Keep `py-agent-ctrl` as a direct subprocess library, but evolve the core around
four explicit layers:

- `AgentCtrl` facade and provider-specific fluent builders.
- `CommandSpec` and provider-specific command/env builders.
- `CommandExecutor` with host and future sandbox drivers, timeout/cancellation,
  stderr tail capture, log/wiretap hooks, and JSONL parsing diagnostics.
- Normalized event/result projection with provider-specific raw event retention.

ACP should be treated as an optional adapter/projection target, not as the core
runtime dependency until there is a clear need to interoperate with ACP clients.

See the per-project notes:

- [myclaude-codeagent-wrapper.md](myclaude-codeagent-wrapper.md)
- [hapi.md](hapi.md)
- [agent-client-protocol.md](agent-client-protocol.md)
- [claude-agent-sdk-python.md](claude-agent-sdk-python.md)
- [missed-problems.md](missed-problems.md)
