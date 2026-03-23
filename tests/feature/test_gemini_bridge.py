from py_agent_ctrl import AgentCtrl

from tests.feature.helpers import install_fake_cli, prepend_path


def test_gemini_execute_via_fake_binary(tmp_path, monkeypatch):
    install_fake_cli(
        tmp_path,
        "gemini",
        [
            '{"type":"init","session_id":"gemini-session"}',
            '{"type":"message","role":"assistant","content":"Hello","delta":true}',
            '{"type":"result","status":"success","stats":{"total_tokens":100,"input_tokens":40,"output_tokens":60,"cached":5}}',
        ],
    )
    prepend_path(tmp_path, monkeypatch)

    response = AgentCtrl.gemini().execute("hello")

    assert response.text == "Hello"
    assert response.session_id == "gemini-session"
    assert response.usage.cache_read_tokens == 5
