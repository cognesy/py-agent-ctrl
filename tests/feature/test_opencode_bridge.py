from py_agent_ctrl import AgentCtrl

from tests.feature.helpers import install_fake_cli, prepend_path


def test_opencode_execute_via_fake_binary(tmp_path, monkeypatch):
    install_fake_cli(
        tmp_path,
        "opencode",
        [
            '{"type":"text","timestamp":2,"sessionID":"sess_stream","part":{"messageID":"msg_1","id":"part_2","text":"Hello OpenCode"}}',
            '{"type":"step_finish","timestamp":4,"sessionID":"sess_stream","part":{"messageID":"msg_1","id":"part_4","cost":0.42,"tokens":{"input":11,"output":5,"reasoning":1,"cache":{"read":2,"write":1}}}}',
        ],
    )
    prepend_path(tmp_path, monkeypatch)

    response = AgentCtrl.opencode().execute("hello")

    assert response.text == "Hello OpenCode"
    assert response.session_id == "sess_stream"
    assert response.cost_usd == 0.42
