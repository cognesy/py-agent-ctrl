from py_agent_ctrl import AgentCtrl, AgentType
from py_agent_ctrl.actions.agents import CodexAction, OpenCodeAction


def test_claude_capabilities_are_exposed_from_new_package_root():
    capabilities = AgentCtrl.claude_code().capabilities()

    assert capabilities.agent_type == AgentType.CLAUDE_CODE
    assert capabilities.cli_name == "claude"


def test_placeholder_capabilities_exist_for_future_bridges():
    capabilities = AgentCtrl.codex().capabilities()

    assert capabilities.agent_type == AgentType.CODEX
    assert capabilities.cli_name == "codex"


def test_make_selects_builder_by_agent_type():
    action = AgentCtrl.make(AgentType.CODEX)

    assert isinstance(action, CodexAction)


def test_make_accepts_agent_type_string():
    action = AgentCtrl.make("opencode")

    assert isinstance(action, OpenCodeAction)


def test_open_code_alias_matches_opencode_builder():
    action = AgentCtrl.open_code()

    assert isinstance(action, OpenCodeAction)
