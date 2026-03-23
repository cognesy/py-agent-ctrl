from __future__ import annotations

from py_agent_ctrl.api.models import AgentRequest
from py_agent_ctrl.services.core.binaries import require_binary


def build_opencode_command(request: AgentRequest) -> list[str]:
    opencode = require_binary("opencode", "Install the OpenCode CLI and ensure `opencode` is on PATH.")
    argv = [opencode, "run", "--format", "json"]
    if request.model:
        argv.extend(["--model", request.model])
    agent = request.provider_options.get("agent")
    if agent:
        argv.extend(["--agent", str(agent)])
    for file in request.provider_options.get("files", []):
        argv.extend(["--file", file])
    if request.continue_session:
        argv.append("--continue")
    elif request.resume_session_id:
        argv.extend(["--session", request.resume_session_id])
    if request.provider_options.get("share_session"):
        argv.append("--share")
    title = request.provider_options.get("title")
    if title:
        argv.extend(["--title", str(title)])
    attach_url = request.provider_options.get("attach_url")
    if attach_url:
        argv.extend(["--attach", str(attach_url)])
    port = request.provider_options.get("port")
    if port is not None:
        argv.extend(["--port", str(port)])
    command = request.provider_options.get("command")
    if command:
        argv.extend(["--command", str(command)])
    argv.append(request.prompt)
    return argv
