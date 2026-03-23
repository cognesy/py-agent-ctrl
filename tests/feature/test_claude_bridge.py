from py_agent_ctrl import AgentCtrl

from tests.feature.helpers import install_fake_cli, prepend_path


def test_claude_execute_via_fake_binary(tmp_path, monkeypatch):
    install_fake_cli(
        tmp_path,
        "claude",
        [
            '{"type":"system","subtype":"init","session_id":"abc","tools":[]}',
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"pong"}]}}',
            '{"type":"result","subtype":"success","session_id":"abc","result":"pong","is_error":false,"cost_usd":null,"duration_ms":800}',
        ],
    )
    prepend_path(tmp_path, monkeypatch)

    response = AgentCtrl.claude_code().execute("hello")

    assert response.text == "pong"
    assert response.session_id == "abc"
