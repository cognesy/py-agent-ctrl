
from py_agent_ctrl.api.models import AgentRequest
from py_agent_ctrl.services.bridges.codex.command_builder import build_codex_command
from py_agent_ctrl.services.bridges.gemini.command_builder import build_gemini_command
from py_agent_ctrl.services.bridges.opencode.command_builder import build_opencode_command
from py_agent_ctrl.services.bridges.pi.command_builder import build_pi_command


def _patch(monkeypatch, module, binary):
    monkeypatch.setattr(f"{module}.require_binary", lambda *_a, **_kw: f"/tmp/{binary}")


# ── Codex ──────────────────────────────────────────────────────────────────


def test_codex_normal_has_no_resume_subcommand(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.codex.command_builder", "codex")
    argv = build_codex_command(AgentRequest(prompt="go"))
    assert argv[:3] == ["/tmp/codex", "exec", "go"]
    assert "resume" not in argv


def test_codex_continue_uses_resume_last(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.codex.command_builder", "codex")
    argv = build_codex_command(AgentRequest(prompt="go", continue_session=True))
    assert argv[2] == "resume"
    assert argv[3] == "--last"
    assert "go" in argv


def test_codex_resume_uses_session_id(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.codex.command_builder", "codex")
    argv = build_codex_command(AgentRequest(prompt="go", resume_session_id="sid-1"))
    assert argv[2] == "resume"
    assert argv[3] == "sid-1"
    assert "go" in argv


# ── Gemini ─────────────────────────────────────────────────────────────────


def test_gemini_normal_has_no_resume_flag(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.gemini.command_builder", "gemini")
    argv = build_gemini_command(AgentRequest(prompt="go"))
    assert "--resume" not in argv


def test_gemini_continue_uses_resume_last(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.gemini.command_builder", "gemini")
    argv = build_gemini_command(AgentRequest(prompt="go", continue_session=True))
    assert argv[argv.index("--resume") + 1] == "last"


def test_gemini_resume_uses_session_id(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.gemini.command_builder", "gemini")
    argv = build_gemini_command(AgentRequest(prompt="go", resume_session_id="g-session"))
    assert argv[argv.index("--resume") + 1] == "g-session"


# ── OpenCode ───────────────────────────────────────────────────────────────


def test_opencode_normal_has_no_session_flags(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.opencode.command_builder", "opencode")
    argv = build_opencode_command(AgentRequest(prompt="go"))
    assert "--continue" not in argv
    assert "--session" not in argv


def test_opencode_continue_flag(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.opencode.command_builder", "opencode")
    argv = build_opencode_command(AgentRequest(prompt="go", continue_session=True))
    assert "--continue" in argv
    assert "--session" not in argv


def test_opencode_resume_uses_session_flag(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.opencode.command_builder", "opencode")
    argv = build_opencode_command(AgentRequest(prompt="go", resume_session_id="oc-1"))
    assert "--continue" not in argv
    assert argv[argv.index("--session") + 1] == "oc-1"


# ── Pi ─────────────────────────────────────────────────────────────────────


def test_pi_normal_has_no_session_flags(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.pi.command_builder", "pi")
    argv = build_pi_command(AgentRequest(prompt="go"))
    assert "--continue" not in argv
    assert "--session" not in argv


def test_pi_continue_flag(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.pi.command_builder", "pi")
    argv = build_pi_command(AgentRequest(prompt="go", continue_session=True))
    assert "--continue" in argv


def test_pi_resume_uses_session_flag(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.pi.command_builder", "pi")
    argv = build_pi_command(AgentRequest(prompt="go", resume_session_id="pi-1"))
    assert argv[argv.index("--session") + 1] == "pi-1"


def test_pi_system_prompt_only(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.pi.command_builder", "pi")
    argv = build_pi_command(AgentRequest(prompt="go", system_prompt="Base"))
    assert argv[argv.index("--system-prompt") + 1] == "Base"
    assert "--append-system-prompt" not in argv


def test_pi_append_system_prompt_only(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.pi.command_builder", "pi")
    argv = build_pi_command(AgentRequest(prompt="go", append_system_prompt="Extra"))
    assert argv[argv.index("--append-system-prompt") + 1] == "Extra"
    assert "--system-prompt" not in argv


def test_pi_both_system_prompts_emitted(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.pi.command_builder", "pi")
    argv = build_pi_command(AgentRequest(prompt="go", system_prompt="Base", append_system_prompt="Extra"))
    assert "--system-prompt" in argv
    assert "--append-system-prompt" in argv
