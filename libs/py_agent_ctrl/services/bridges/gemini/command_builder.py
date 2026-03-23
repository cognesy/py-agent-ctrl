from __future__ import annotations

from py_agent_ctrl.api.models import AgentRequest
from py_agent_ctrl.services.core.binaries import require_binary


def build_gemini_command(request: AgentRequest) -> list[str]:
    gemini = require_binary("gemini", "Install the Gemini CLI and ensure `gemini` is on PATH.")
    argv = [gemini, "--output-format", "stream-json"]
    if request.model:
        argv.extend(["--model", request.model])
    approval_mode = request.provider_options.get("approval_mode")
    if approval_mode:
        argv.extend(["--approval-mode", str(approval_mode)])
    if request.provider_options.get("sandbox"):
        argv.append("--sandbox")
    for directory in request.provider_options.get("include_directories", []):
        argv.extend(["--include-directories", directory])
    for extension in request.provider_options.get("extensions", []):
        argv.extend(["--extensions", extension])
    for tool in request.provider_options.get("allowed_tools", []):
        argv.extend(["--allowed-tools", tool])
    for server in request.provider_options.get("allowed_mcp_servers", []):
        argv.extend(["--allowed-mcp-server-names", server])
    for policy in request.provider_options.get("policy_files", []):
        argv.extend(["--policy", policy])
    if request.continue_session:
        argv.extend(["--resume", "last"])
    elif request.resume_session_id:
        argv.extend(["--resume", request.resume_session_id])
    if request.provider_options.get("debug"):
        argv.append("--debug")
    argv.extend(["--prompt", request.prompt])
    return argv
