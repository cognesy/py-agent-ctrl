from py_agent_ctrl import AgentCtrl, AgentTextEvent

from tests.integration.live_helpers import LIVE_TEST_PROMPT, assert_live_response, require_live_agent


def test_pi_execute_via_real_cli():
    require_live_agent("pi", "pi")

    response = (
        AgentCtrl.pi()
        .with_provider("anthropic")
        .with_model("sonnet")
        .with_timeout(120)
        .execute(LIVE_TEST_PROMPT)
    )

    assert_live_response(response)


def test_pi_stream_via_real_cli():
    require_live_agent("pi", "pi")

    result = (
        AgentCtrl.pi()
        .with_provider("anthropic")
        .with_model("sonnet")
        .with_timeout(120)
        .stream(LIVE_TEST_PROMPT)
    )
    events = list(result)
    text_events = [e for e in events if isinstance(e, AgentTextEvent)]
    assert len(text_events) > 0
    assert result.exit_code == 0
