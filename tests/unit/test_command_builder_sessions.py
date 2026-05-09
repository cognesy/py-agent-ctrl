from pathlib import Path

import pytest
from py_agent_ctrl.api.models import AgentRequest, image_data_block, image_ref_block, resource_link_block, text_block
from py_agent_ctrl.services.bridges.claude_code.command_builder import build_claude_command
from py_agent_ctrl.services.bridges.codex.bridge import CodexBridge
from py_agent_ctrl.services.bridges.codex.command_builder import build_codex_command
from py_agent_ctrl.services.bridges.gemini.command_builder import build_gemini_command
from py_agent_ctrl.services.bridges.opencode.command_builder import build_opencode_command
from py_agent_ctrl.services.bridges.pi.command_builder import build_pi_command
from py_agent_ctrl.services.core.errors import WorkingDirectoryNotFoundError
from py_agent_ctrl.services.core.paths import normalize_request_paths


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


def test_codex_builder_receives_normalized_paths(monkeypatch, tmp_path):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.codex.command_builder", "codex")
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(tmp_path)

    request = normalize_request_paths(
        AgentRequest(
            prompt="go",
            working_directory="repo",
            additional_directories=["extra", str(tmp_path / "shared")],
        )
    )
    argv = build_codex_command(request)

    assert request.working_directory == str(repo.resolve())
    assert request.additional_directories == [
        str((repo / "extra").resolve(strict=False)),
        str((tmp_path / "shared").resolve(strict=False)),
    ]
    assert argv[argv.index("--cd") + 1] == str(repo.resolve())
    assert argv[argv.index("--add-dir") + 1] == str((repo / "extra").resolve(strict=False))


def test_missing_working_directory_is_rejected_before_binary_lookup(tmp_path):
    with pytest.raises(WorkingDirectoryNotFoundError) as exc_info:
        CodexBridge().execute(AgentRequest(prompt="go", working_directory=str(tmp_path / "missing")))

    assert Path(exc_info.value.cwd) == (tmp_path / "missing").resolve(strict=False)


# ── Structured Content Prompt Fallback ─────────────────────────────────────


def test_structured_content_lowers_to_text_for_all_command_builders(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.claude_code.command_builder", "claude")
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.codex.command_builder", "codex")
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.gemini.command_builder", "gemini")
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.opencode.command_builder", "opencode")
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.pi.command_builder", "pi")
    request = AgentRequest(
        prompt="go",
        content=[
            text_block("Use this context."),
            resource_link_block("file:///tmp/README.md", name="README.md"),
        ],
    )
    expected = "go\n\nUse this context.\n\n[resource: README.md] file:///tmp/README.md"

    claude_argv = build_claude_command(request)

    assert claude_argv[claude_argv.index("-p") + 1] == expected
    assert build_codex_command(request)[2] == expected
    assert build_gemini_command(request)[build_gemini_command(request).index("--prompt") + 1] == expected
    assert build_opencode_command(request)[-1] == expected
    assert build_pi_command(request)[-1] == expected


def test_codex_image_content_emits_native_image_flag_and_keeps_text_fallback(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.codex.command_builder", "codex")
    request = AgentRequest(prompt="inspect", content=[image_ref_block("/tmp/screenshot.png")])

    argv = build_codex_command(request)

    assert argv[2] == "inspect\n\n[image: /tmp/screenshot.png]"
    assert argv[argv.index("--image") + 1] == "/tmp/screenshot.png"


def test_codex_existing_image_provider_option_still_works(monkeypatch):
    _patch(monkeypatch, "py_agent_ctrl.services.bridges.codex.command_builder", "codex")
    request = AgentRequest(
        prompt="inspect",
        content=[image_data_block("iVBORw0KGgo=", mime_type="image/png")],
        provider_options={"images": ["/tmp/existing.png"]},
    )

    argv = build_codex_command(request)

    assert argv[2] == "inspect\n\n[image: <image/png>]"
    assert argv[argv.index("--image") + 1] == "/tmp/existing.png"
    assert "iVBORw0KGgo=" not in argv


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
