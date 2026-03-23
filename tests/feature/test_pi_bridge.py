from py_agent_ctrl import AgentCtrl

from tests.feature.helpers import install_fake_cli, prepend_path


def test_pi_execute_via_fake_binary(tmp_path, monkeypatch):
    install_fake_cli(
        tmp_path,
        "pi",
        [
            '{"type":"session","version":3,"id":"pi-session","cwd":"/tmp","timestamp":"2025-01-01T00:00:00Z"}',
            '{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"Hello"},"message":{}}',
            '{"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":" world"}],"usage":{"input":3,"output":5,"cacheRead":0,"cacheWrite":2,"totalTokens":10,"cost":{"total":0.12}}}}',
        ],
    )
    prepend_path(tmp_path, monkeypatch)

    response = AgentCtrl.pi().execute("hello")

    assert response.text == "Hello world"
    assert response.session_id == "pi-session"
    assert response.usage.total_tokens == 10
