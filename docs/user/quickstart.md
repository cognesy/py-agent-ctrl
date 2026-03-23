# Quick Start

## Python

```python
from py_agent_ctrl import AgentCtrl

response = AgentCtrl.claude_code().execute("Summarize this repository.")
print(response.text)
```

## CLI

```bash
uv run ctrlagent execute --agent claude-code "Summarize this repository."
```

## Common Builder Methods

- `.with_model(...)`
- `.with_system_prompt(...)`
- `.append_system_prompt(...)`
- `.with_max_turns(...)`
- `.in_directory(...)`
- `.with_additional_dirs([...])`
- `.with_timeout(...)`
- `.resume_session(...)`
- `.continue_session()`

## Agent-Specific Methods

- Claude Code: `.with_permission_mode(...)`, `.with_allowed_tools(...)`
- Codex: `.with_sandbox(...)`, `.full_auto()`, `.dangerously_bypass()`, `.with_images([...])`
- OpenCode: `.with_agent(...)`, `.with_files([...])`, `.with_title(...)`, `.share_session()`
- Pi: `.with_provider(...)`, `.with_thinking(...)`, `.with_tools([...])`, `.with_extensions([...])`, `.with_skills([...])`
- Gemini: `.with_approval_mode(...)`, `.plan_mode()`, `.yolo()`, `.with_sandbox()`, `.with_allowed_tools([...])`
