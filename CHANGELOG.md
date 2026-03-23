# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-23

### Added

- `AgentCtrl` facade with five bridge factories: `claude_code()`, `codex()`, `opencode()`, `pi()`, `gemini()`
- Fluent immutable builder pattern on all action classes with base methods: `with_model`,
  `with_system_prompt`, `append_system_prompt`, `with_max_turns`, `in_directory`,
  `with_additional_dirs`, `with_timeout`, `resume_session`, `continue_session`
- Agent-specific builder methods — Claude Code: `with_permission_mode`, `with_allowed_tools`;
  Codex: `with_sandbox`, `full_auto`, `dangerously_bypass`, `skip_git_repo_check`, `with_images`;
  OpenCode: `with_agent`, `with_files`, `with_title`, `share_session`;
  Pi: `with_provider`, `with_thinking`, `with_tools`, `with_extensions`, `with_skills`, `ephemeral`, `with_session_dir`;
  Gemini: `with_approval_mode`, `plan_mode`, `yolo`, `with_sandbox`, `with_allowed_tools`
- `execute(prompt)` — blocking subprocess call returning `AgentResponse`
- `stream(prompt)` — real-time line-by-line streaming via `subprocess.Popen`, returns `StreamResult`
- `StreamResult` — iterable of `AgentEvent` with `.exit_code` accessible after iterator exhaustion
- Subprocess watchdog timeout: `threading.Timer` kills hung processes regardless of output flow
- `AgentResponse` model with fields: `text`, `exit_code`, `session_id`, `usage` (`TokenUsage`),
  `tool_calls`, `cost_usd`, `duration_ms`, `parse_failures`, `parse_failure_samples`
- `TokenUsage` model: `input_tokens`, `output_tokens`, `total_tokens`, `cache_read_tokens`,
  `cache_write_tokens`, `reasoning_tokens`
- `AgentTextEvent`, `AgentToolCallEvent`, `AgentResultEvent`, `AgentUnknownEvent` normalized event types
- Gemini streaming: stateful `tool_use`/`tool_result` pairing yields `AgentToolCallEvent` in real time
- `AgentError` and `BinaryNotFoundError` structured exception hierarchy (both subclass `RuntimeError`)
- Session continuity: `resume_session(id)` and `continue_session()` supported across all five bridges
- `ctrlagent` CLI with commands: `execute`, `stream`, `resume`, `continue`,
  `agents list`, `agents capabilities`
- 82 unit and feature tests; 10 integration smoke tests (skip automatically without live CLI binaries)
- GitHub Actions CI pipeline: `ruff check`, `mypy --strict`, `pytest` on push and PR to `main`
- PEP 561 `py.typed` marker for IDE type inference from installed package
- Full mypy strict-mode compliance across all 41 source files
