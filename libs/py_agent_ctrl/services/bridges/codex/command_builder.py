from __future__ import annotations

from py_agent_ctrl.api.models import AgentRequest
from py_agent_ctrl.services.core.binaries import require_binary


def build_codex_command(request: AgentRequest) -> list[str]:
    codex = require_binary("codex", "Install the Codex CLI and ensure `codex` is on PATH.")
    argv = [codex, "exec"]

    if request.continue_session or request.resume_session_id:
        argv.append("resume")
        if request.continue_session:
            argv.append("--last")
        else:
            argv.append(request.resume_session_id or "")

    argv.append(request.prompt)

    sandbox = request.provider_options.get("sandbox")
    if sandbox:
        argv.extend(["--sandbox", str(sandbox)])
    if request.model:
        argv.extend(["--model", request.model])
    for image in request.provider_options.get("images", []):
        argv.extend(["--image", image])
    if request.working_directory:
        argv.extend(["--cd", request.working_directory])
    for directory in request.additional_directories:
        argv.extend(["--add-dir", directory])
    if request.provider_options.get("full_auto"):
        argv.append("--full-auto")
    if request.provider_options.get("dangerously_bypass"):
        argv.append("--dangerously-bypass-approvals-and-sandbox")
    if request.provider_options.get("skip_git_repo_check"):
        argv.append("--skip-git-repo-check")
    for key, value in request.provider_options.get("config_overrides", {}).items():
        argv.extend(["--config", f"{key}={value}"])

    return argv
