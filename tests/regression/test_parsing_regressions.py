from py_agent_ctrl.api.models import AgentRequest
from py_agent_ctrl.services.bridges.claude_code.bridge import ClaudeCodeBridge
from py_agent_ctrl.services.bridges.codex.bridge import CodexBridge
from py_agent_ctrl.services.bridges.gemini.bridge import GeminiBridge
from py_agent_ctrl.services.bridges.opencode.bridge import OpenCodeBridge
from py_agent_ctrl.services.bridges.pi.bridge import PiBridge


def test_claude_counts_malformed_json_without_losing_valid_text(monkeypatch):
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.claude_code.command_builder.build_claude_command",
        lambda _request: ["claude", "-p", "ignored"],
    )
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.claude_code.bridge.run_process",
        lambda *args, **kwargs: type("Output", (), {
            "exit_code": 0,
            "stdout": '\n'.join([
                '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"pong"}]}}',
                "not-json",
                '{"type":"result","subtype":"success","session_id":"abc","result":"pong","is_error":false}',
            ]),
            "stderr": "",
        })(),
    )

    response = ClaudeCodeBridge().execute(AgentRequest(prompt="ignored"))

    assert response.text == "pong"
    assert response.parse_failures == 1
    assert response.parse_failure_samples == ["not-json"]


def test_codex_counts_malformed_json_without_losing_valid_thread(monkeypatch):
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.codex.command_builder.build_codex_command",
        lambda _request: ["codex", "exec", "ignored"],
    )
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.codex.bridge.run_process",
        lambda *args, **kwargs: type("Output", (), {
            "exit_code": 0,
            "stdout": '\n'.join([
                '{"type":"thread.started","thread_id":"thread_stream"}',
                "not-json",
                '{"type":"item.completed","item":{"id":"msg_1","type":"agent_message","status":"completed","text":"Hello from codex"}}',
            ]),
            "stderr": "",
        })(),
    )

    response = CodexBridge().execute(AgentRequest(prompt="ignored"))

    assert response.session_id == "thread_stream"
    assert response.text == "Hello from codex"
    assert response.parse_failures == 1


def test_codex_accepts_plain_json_final_output(monkeypatch):
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.codex.command_builder.build_codex_command",
        lambda _request: ["codex", "exec", "ignored"],
    )
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.codex.bridge.run_process",
        lambda *args, **kwargs: type("Output", (), {
            "exit_code": 0,
            "stdout": '{"directories":["py-agent-ctrl","xcron"]}',
            "stderr": "",
        })(),
    )

    response = CodexBridge().execute(AgentRequest(prompt="ignored"))

    assert response.text == '{"directories": ["py-agent-ctrl", "xcron"]}'
    assert response.parse_failures == 0


def test_pi_ignores_user_echo_and_keeps_final_assistant_json(monkeypatch):
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.pi.command_builder.build_pi_command",
        lambda _request: ["pi", "--mode", "json", "ignored"],
    )
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.pi.bridge.run_process",
        lambda *args, **kwargs: type("Output", (), {
            "exit_code": 0,
            "stdout": "\n".join([
                '{"type":"session","version":3,"id":"pi-session"}',
                '{"type":"message_end","message":{"role":"user","content":[{"type":"text","text":"prompt"}]}}',
                '{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"{\\"directories\\":[\\"py-agent-ctrl\\"]}"},"message":{}}',
                '{"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":"{\\"directories\\":[\\"py-agent-ctrl\\"]}"}],"usage":{"input":1,"output":1,"totalTokens":2}}}',
            ]),
            "stderr": "",
        })(),
    )

    response = PiBridge().execute(AgentRequest(prompt="ignored"))

    assert response.text == '{"directories":["py-agent-ctrl"]}'
    assert response.session_id == "pi-session"


def test_gemini_extracts_text_and_tool_call_ignoring_malformed_json(monkeypatch):
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.gemini.command_builder.build_gemini_command",
        lambda _request: ["gemini", "ignored"],
    )
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.gemini.bridge.run_process",
        lambda *args, **kwargs: type("Output", (), {
            "exit_code": 0,
            "stdout": "\n".join([
                '{"type":"init","session_id":"g1"}',
                '{"type":"message","role":"assistant","content":"thinking","delta":true}',
                "not-json",
                '{"type":"tool_use","tool_name":"read_file","tool_id":"t1","parameters":{"path":"x"}}',
                '{"type":"tool_result","tool_id":"t1","status":"success","output":"file-data"}',
                '{"type":"result","status":"success"}',
            ]),
            "stderr": "",
        })(),
    )

    response = GeminiBridge().execute(AgentRequest(prompt="ignored"))

    assert response.text == "thinking"
    assert response.parse_failures == 1
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "read_file"
    assert response.tool_calls[0].output == "file-data"


def test_opencode_extracts_text_and_usage_from_step_finish(monkeypatch):
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.opencode.command_builder.build_opencode_command",
        lambda _request: ["opencode", "ignored"],
    )
    monkeypatch.setattr(
        "py_agent_ctrl.services.bridges.opencode.bridge.run_process",
        lambda *args, **kwargs: type("Output", (), {
            "exit_code": 0,
            "stdout": "\n".join([
                '{"type":"text","sessionID":"oc1","part":{"text":"hello opencode"}}',
                '{"type":"step_finish","sessionID":"oc1","part":{"cost":0.02,"tokens":{"input":10,"output":5,"reasoning":0,"cache":{"read":2,"write":1}}}}',
            ]),
            "stderr": "",
        })(),
    )

    response = OpenCodeBridge().execute(AgentRequest(prompt="ignored"))

    assert response.text == "hello opencode"
    assert response.session_id == "oc1"
    assert response.cost_usd == 0.02
    assert response.usage is not None
    assert response.usage.input_tokens == 10
    assert response.usage.output_tokens == 5
    assert response.usage.cache_read_tokens == 2
    assert response.usage.cache_write_tokens == 1
