# Claude Agent SDK Python

Local reference:
`/Users/ddebowczyk/projects/_ext/claude-agent-sdk-python`

## Fit

This is a provider-specific SDK, not a multi-agent abstraction. It is still the
best reference for how deep a mature provider-native Python surface can be.

## Relevant Design

Typed option surface:

- `ClaudeAgentOptions` includes tools, allowed/disallowed tools, system prompt
  variants, MCP servers, permission mode, continue/resume/session ID,
  max turns/budget, model/fallback model, betas, cwd, CLI path, settings,
  additional directories, env, extra args, max buffer size, stderr callback,
  tool permission callback, hooks, user, partial messages, session forking,
  custom agents, setting sources, sandbox settings, plugins, thinking/effort,
  output format, file checkpointing, and task budget.
- This supports provider-native controls without pretending every agent shares
  one option set.

Subprocess transport:

- `_internal/transport/subprocess_cli.py` finds a bundled CLI first, then a
  system CLI, then common install locations.
- It performs a version check with a timeout.
- It builds stream-json commands with `--input-format stream-json` and sends
  large/dynamic config through the initialize/control protocol.
- It filters `CLAUDECODE` from inherited env so nested SDK launches do not look
  like they are running inside Claude Code.
- It can route stderr into a callback.
- It validates missing working directories separately from missing CLI binaries.
- It buffers partial JSON until it can parse a complete object and has a max
  buffer size.
- It skips non-JSON stdout lines when not in the middle of parsing.
- It closes stdin with a lock, waits for graceful process shutdown to let the
  CLI flush session files, then escalates to terminate and kill.

Control protocol and parsing:

- `_internal/client.py` always initializes streaming mode internally and supports
  hooks, SDK MCP servers, custom agents, and permission callbacks.
- `_internal/query.py` routes control requests/responses, hook callbacks,
  permission callbacks, and message streaming. It tracks pending control
  responses and child tasks.
- `_internal/message_parser.py` parses user, assistant, system, result,
  stream_event, and rate_limit_event messages into typed objects, skipping
  unknown message types for forward compatibility.

Session management:

- `_internal/sessions.py` reads session metadata and reconstructs visible
  messages from JSONL transcript chains.
- `_internal/session_mutations.py` supports rename, tag, delete, and fork by
  appending typed metadata entries or remapping UUID chains.
- Session-forking explicitly filters sidechains and progress messages.

Error taxonomy:

- `_errors.py` separates `CLINotFoundError`, `CLIConnectionError`,
  `ProcessError`, `CLIJSONDecodeError`, and `MessageParseError`.

## What To Borrow

- Keep provider-specific options broad and typed. For Python, that can be
  specialized action methods plus optional typed provider option models later.
- Add stderr callbacks separately from text/event callbacks.
- Add provider CLI version preflight where version compatibility matters.
- Add partial JSON buffering with a maximum size, not only line-by-line parsing.
- Add a richer error hierarchy with parse errors distinct from process errors.
- Treat session metadata as a first-class concept if we add session management
  APIs beyond `resume_session`.
- Add a forward-compatible parse policy: preserve unknown raw events without
  failing older clients by default.

## What Not To Copy Directly

- Do not import the Claude SDK as the cross-provider core. It is intentionally
  Claude-specific and has many controls that do not translate to Codex, Gemini,
  Pi, or OpenCode.
- Do not force all providers into Claude's hook/control-protocol semantics.
- Do not add every Claude option to the common builder. Keep them on
  `ClaudeCodeAction`.

## Gaps Relative To py-agent-ctrl

`py-agent-ctrl` has a much smaller option surface and simpler process handling.
It needs deeper provider-specific options, better stderr/process error taxonomy,
partial JSON buffering, and optional session metadata APIs before it reaches the
same maturity for Claude alone.
