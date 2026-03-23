from __future__ import annotations

import shutil

from py_agent_ctrl.api.models import AgentRequest
from py_agent_ctrl.services.core.binaries import require_binary


def build_claude_command(request: AgentRequest) -> list[str]:
    claude = require_binary("claude", "Install: npm install -g @anthropic-ai/claude-code")
    argv: list[str] = []

    if shutil.which("stdbuf"):
        argv.extend(["stdbuf", "-o0"])

    argv.extend([claude, "-p", request.prompt, "--output-format", "stream-json", "--verbose"])

    if request.continue_session:
        argv.append("--continue")
    elif request.resume_session_id:
        argv.extend(["--resume", request.resume_session_id])

    if request.model:
        argv.extend(["--model", request.model])
    if request.system_prompt:
        argv.extend(["--system-prompt", request.system_prompt])
    elif request.append_system_prompt:
        argv.extend(["--append-system-prompt", request.append_system_prompt])
    if request.max_turns is not None:
        argv.extend(["--max-turns", str(request.max_turns)])

    permission_mode = request.provider_options.get("permission_mode")
    if permission_mode and permission_mode != "default":
        argv.extend(["--permission-mode", str(permission_mode)])

    allowed_tools = request.provider_options.get("allowed_tools")
    if allowed_tools:
        argv.extend(["--allowedTools", ",".join(str(tool) for tool in allowed_tools)])

    for directory in request.additional_directories:
        argv.extend(["--add-dir", directory])

    return argv
