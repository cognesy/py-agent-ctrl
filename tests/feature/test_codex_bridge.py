from py_agent_ctrl import AgentCtrl

from tests.feature.helpers import install_fake_cli, prepend_path


def test_codex_execute_via_fake_binary(tmp_path, monkeypatch):
    install_fake_cli(
        tmp_path,
        "codex",
        [
            '{"type":"thread.started","thread_id":"thread_stream"}',
            '{"type":"item.completed","item":{"id":"msg_1","type":"agent_message","status":"completed","text":"Hello from codex"}}',
            '{"type":"turn.completed","usage":{"input_tokens":9,"cached_input_tokens":3,"output_tokens":2}}',
        ],
    )
    prepend_path(tmp_path, monkeypatch)

    response = AgentCtrl.codex().execute("hello")

    assert response.text == "Hello from codex"
    assert response.session_id == "thread_stream"
    assert response.usage.input_tokens == 9
