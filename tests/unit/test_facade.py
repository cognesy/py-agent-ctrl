from py_agent_ctrl import AgentCtrl, AgentType


def test_claude_capabilities_are_exposed_from_new_package_root():
    capabilities = AgentCtrl.claude_code().capabilities()

    assert capabilities.agent_type == AgentType.CLAUDE_CODE
    assert capabilities.cli_name == "claude"


def test_placeholder_capabilities_exist_for_future_bridges():
    capabilities = AgentCtrl.codex().capabilities()

    assert capabilities.agent_type == AgentType.CODEX
    assert capabilities.cli_name == "codex"
