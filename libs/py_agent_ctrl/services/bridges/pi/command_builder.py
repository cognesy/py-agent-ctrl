from __future__ import annotations

from py_agent_ctrl.api.models import AgentRequest
from py_agent_ctrl.services.core.binaries import require_binary


def build_pi_command(request: AgentRequest) -> list[str]:
    pi = require_binary("pi", "Install the Pi CLI and ensure `pi` is on PATH.")
    argv = [pi, "--mode", "json"]
    if request.model:
        argv.extend(["--model", request.model])
    provider = request.provider_options.get("provider")
    if provider:
        argv.extend(["--provider", str(provider)])
    thinking = request.provider_options.get("thinking")
    if thinking:
        argv.extend(["--thinking", str(thinking)])
    if request.system_prompt:
        argv.extend(["--system-prompt", request.system_prompt])
    if request.append_system_prompt:
        argv.extend(["--append-system-prompt", request.append_system_prompt])
    if request.provider_options.get("no_tools"):
        argv.append("--no-tools")
    elif request.provider_options.get("tools"):
        argv.extend(["--tools", ",".join(request.provider_options["tools"])])
    if request.provider_options.get("no_extensions"):
        argv.append("--no-extensions")
    for extension in request.provider_options.get("extensions", []):
        argv.extend(["-e", extension])
    if request.provider_options.get("no_skills"):
        argv.append("--no-skills")
    for skill in request.provider_options.get("skills", []):
        argv.extend(["--skill", skill])
    api_key = request.provider_options.get("api_key")
    if api_key:
        argv.extend(["--api-key", str(api_key)])
    if request.provider_options.get("no_session"):
        argv.append("--no-session")
    session_dir = request.provider_options.get("session_dir")
    if session_dir:
        argv.extend(["--session-dir", str(session_dir)])
    if request.continue_session:
        argv.append("--continue")
    elif request.resume_session_id:
        argv.extend(["--session", request.resume_session_id])
    if request.provider_options.get("verbose", True):
        argv.append("--verbose")
    for file in request.provider_options.get("files", []):
        argv.append(f"@{file}")
    argv.append(request.prompt)
    return argv
