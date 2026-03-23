from py_agent_ctrl.api.models import AgentRequest
from py_agent_ctrl.services.bridges.claude_code.command_builder import build_claude_command


def _patch_binary(monkeypatch):
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.claude_code.command_builder.require_binary",
        lambda *_args, **_kwargs: "/tmp/claude",
    )
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.claude_code.command_builder.shutil.which",
        lambda name: None if name == "stdbuf" else f"/tmp/{name}",
    )


def test_resume_session_flag_is_added(monkeypatch):
    _patch_binary(monkeypatch)
    request = AgentRequest(prompt="x", resume_session_id="abc-123")

    argv = build_claude_command(request)

    assert argv[argv.index("--resume") + 1] == "abc-123"


def test_continue_takes_precedence_over_resume(monkeypatch):
    _patch_binary(monkeypatch)
    request = AgentRequest(prompt="x", resume_session_id="abc-123", continue_session=True)

    argv = build_claude_command(request)

    assert "--continue" in argv
    assert "--resume" not in argv


def test_permission_mode_and_allowed_tools_are_added(monkeypatch):
    _patch_binary(monkeypatch)
    request = AgentRequest(
        prompt="x",
        provider_options={"permission_mode": "bypassPermissions", "allowed_tools": ["Read", "Edit"]},
    )

    argv = build_claude_command(request)

    assert argv[argv.index("--permission-mode") + 1] == "bypassPermissions"
    assert argv[argv.index("--allowedTools") + 1] == "Read,Edit"


def test_system_prompt_beats_append_system_prompt(monkeypatch):
    _patch_binary(monkeypatch)
    request = AgentRequest(prompt="x", system_prompt="Full", append_system_prompt="Append")

    argv = build_claude_command(request)

    assert argv[argv.index("--system-prompt") + 1] == "Full"
    assert "--append-system-prompt" not in argv


def test_additional_directories_are_emitted(monkeypatch):
    _patch_binary(monkeypatch)
    request = AgentRequest(prompt="x", additional_directories=["/tmp/a", "/tmp/b"])

    argv = build_claude_command(request)

    assert argv.count("--add-dir") == 2
