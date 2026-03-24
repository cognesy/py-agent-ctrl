import os

from py_agent_ctrl import AgentCtrl, AgentResultEvent, AgentTextEvent, StreamResult
from py_agent_ctrl.api.events import AgentToolCallEvent
from py_agent_ctrl.services.core.subprocess import stream_process

from tests.feature.helpers import install_fake_cli, prepend_path


def test_claude_stream_yields_text_and_result_events(tmp_path, monkeypatch):
    install_fake_cli(
        tmp_path,
        "claude",
        [
            '{"type":"system","subtype":"init","session_id":"s1","tools":[]}',
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"hello"}]}}',
            '{"type":"result","subtype":"success","session_id":"s1","result":"hello","is_error":false,"cost_usd":0.01,"duration_ms":100}',
        ],
    )
    prepend_path(tmp_path, monkeypatch)

    result = AgentCtrl.claude_code().stream("ping")
    assert isinstance(result, StreamResult)
    events = list(result)

    text_events = [e for e in events if isinstance(e, AgentTextEvent)]
    result_events = [e for e in events if isinstance(e, AgentResultEvent)]
    assert text_events[0].text == "hello"
    assert result_events[0].session_id == "s1"
    assert result.exit_code == 0


def test_stream_exit_code_propagated_on_failure(tmp_path, monkeypatch):
    script = tmp_path / "claude"
    script.write_text(
        "#!/bin/sh\nprintf '%s\\n' '{\"type\":\"result\",\"subtype\":\"error\",\"session_id\":\"\",\"result\":\"\",\"is_error\":true}'\nexit 1\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    prepend_path(tmp_path, monkeypatch)

    result = AgentCtrl.claude_code().stream("fail")
    list(result)  # exhaust the iterator
    assert result.exit_code == 1


def test_stream_process_skips_non_json_lines(tmp_path):
    install_fake_cli(
        tmp_path,
        "myagent",
        [
            "not json",
            '{"type":"ok"}',
            "also not json",
        ],
    )

    gen, get_exit_code = stream_process(
        [str(tmp_path / "myagent")],
        cwd=None,
        env=dict(os.environ),
        timeout_seconds=10,
    )
    results = list(gen)
    payloads = [p for p, _ in results]
    assert payloads[0] is None
    assert payloads[1] == {"type": "ok"}
    assert payloads[2] is None
    assert get_exit_code() == 0


def test_codex_stream_yields_text_events(tmp_path, monkeypatch):
    install_fake_cli(
        tmp_path,
        "codex",
        [
            '{"type":"thread.started","thread_id":"t1"}',
            '{"type":"item.completed","item":{"id":"m1","type":"agent_message","status":"completed","text":"streamed"}}',
            '{"type":"turn.completed","usage":{"input_tokens":5,"output_tokens":2}}',
        ],
    )
    prepend_path(tmp_path, monkeypatch)

    result = AgentCtrl.codex().stream("go")
    text_events = [e for e in result if isinstance(e, AgentTextEvent)]
    assert text_events[0].text == "streamed"
    assert result.exit_code == 0


def test_gemini_stream_yields_text_and_result_events(tmp_path, monkeypatch):
    install_fake_cli(
        tmp_path,
        "gemini",
        [
            '{"type":"init","session_id":"g1"}',
            '{"type":"message","role":"assistant","content":"thinking","delta":true}',
            '{"type":"tool_use","tool_name":"read_file","tool_id":"t1","parameters":{"path":"x"}}',
            '{"type":"tool_result","tool_id":"t1","status":"success","output":"data"}',
            '{"type":"result","status":"success"}',
        ],
    )
    prepend_path(tmp_path, monkeypatch)

    result = AgentCtrl.gemini().stream("go")
    events = list(result)

    text_events = [e for e in events if isinstance(e, AgentTextEvent)]
    result_events = [e for e in events if isinstance(e, AgentResultEvent)]
    tool_events = [e for e in events if isinstance(e, AgentToolCallEvent)]
    assert text_events[0].text == "thinking"
    assert len(result_events) >= 1  # init and result events both parse as AgentResultEvent
    assert len(tool_events) == 1
    assert tool_events[0].tool_call.name == "read_file"
    assert tool_events[0].tool_call.output == "data"
    assert result.exit_code == 0


def test_opencode_stream_yields_text_events(tmp_path, monkeypatch):
    install_fake_cli(
        tmp_path,
        "opencode",
        [
            '{"type":"text","sessionID":"oc1","part":{"text":"hello opencode"}}',
            '{"type":"step_finish","sessionID":"oc1","part":{"cost":0.01,"tokens":{}}}',
        ],
    )
    prepend_path(tmp_path, monkeypatch)

    result = AgentCtrl.opencode().stream("go")
    text_events = [e for e in result if isinstance(e, AgentTextEvent)]

    assert text_events[0].text == "hello opencode"
    assert result.exit_code == 0


def test_pi_stream_yields_text_events(tmp_path, monkeypatch):
    install_fake_cli(
        tmp_path,
        "pi",
        [
            '{"type":"session","version":3,"id":"pi-s1","cwd":"/tmp","timestamp":"2025-01-01T00:00:00Z"}',
            '{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"hello pi"},"message":{}}',
            '{"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":"hello pi"}]}}',
        ],
    )
    prepend_path(tmp_path, monkeypatch)

    result = AgentCtrl.pi().stream("go")
    text_events = [e for e in result if isinstance(e, AgentTextEvent)]

    assert text_events[0].text == "hello pi"
    assert result.exit_code == 0
