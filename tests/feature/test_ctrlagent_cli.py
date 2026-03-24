import pytest
from py_agent_ctrl.api.models import AgentResponse, AgentType
from py_agent_ctrl.cli import main

from tests.feature.helpers import install_fake_cli, prepend_path


def test_ctrlagent_execute_uses_claude_bridge(monkeypatch, capsys):
    called = {}

    def fake_execute(self, request):
        called["prompt"] = request.prompt
        return AgentResponse(agent_type=AgentType.CLAUDE_CODE, text="cli-response", exit_code=0)

    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.claude_code.bridge.ClaudeCodeBridge.execute",
        fake_execute,
    )

    exit_code = main(["execute", "--agent", "claude-code", "hello"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert called["prompt"] == "hello"
    assert captured.out.strip() == "cli-response"


def test_ctrlagent_capabilities_prints_json(capsys):
    exit_code = main(["agents", "capabilities", "--agent", "codex"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"agent_type": "codex"' in captured.out


def test_ctrlagent_resume_calls_bridge_with_session(monkeypatch, capsys, tmp_path):
    install_fake_cli(
        tmp_path,
        "claude",
        [
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"resumed"}]}}',
            '{"type":"result","subtype":"success","session_id":"s1","result":"resumed","is_error":false}',
        ],
    )
    prepend_path(tmp_path, monkeypatch)

    exit_code = main(["resume", "--agent", "claude-code", "--session", "s1", "continue this"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "resumed" in captured.out


def test_ctrlagent_continue_calls_bridge(monkeypatch, capsys, tmp_path):
    install_fake_cli(
        tmp_path,
        "claude",
        [
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"continued"}]}}',
            '{"type":"result","subtype":"success","session_id":"s1","result":"continued","is_error":false}',
        ],
    )
    prepend_path(tmp_path, monkeypatch)

    exit_code = main(["continue", "--agent", "claude-code", "next step"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "continued" in captured.out


def test_ctrlagent_stream_prints_text(monkeypatch, capsys, tmp_path):
    install_fake_cli(
        tmp_path,
        "claude",
        [
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"streamed"}]}}',
            '{"type":"result","subtype":"success","session_id":"s1","result":"streamed","is_error":false}',
        ],
    )
    prepend_path(tmp_path, monkeypatch)

    exit_code = main(["stream", "--agent", "claude-code", "ping"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "streamed" in captured.out


def test_ctrlagent_stream_returns_nonzero_exit_code(monkeypatch, tmp_path):
    script = tmp_path / "claude"
    script.write_text(
        "#!/bin/sh\nprintf '%s\\n' '{\"type\":\"result\",\"subtype\":\"error\",\"session_id\":\"\",\"result\":\"\",\"is_error\":true}'\nexit 2\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    prepend_path(tmp_path, monkeypatch)

    exit_code = main(["stream", "--agent", "claude-code", "fail"])

    assert exit_code == 2


def test_ctrlagent_invalid_agent_raises_system_exit():
    with pytest.raises(SystemExit):
        main(["execute", "--agent", "does-not-exist", "x"])
