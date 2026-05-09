from __future__ import annotations

from pathlib import Path

from py_agent_ctrl import AgentCtrl
from py_agent_ctrl.api.models import AgentType
from py_agent_ctrl.cli import main

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_docs_cli_agents_list_example(capsys):
    exit_code = main(["agents", "list"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.splitlines() == [
        "claude-code",
        "codex",
        "opencode",
        "pi",
        "gemini",
    ]


def test_docs_cli_capabilities_example(capsys):
    exit_code = main(["agents", "capabilities", "--agent", "codex"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert '"agent_type": "codex"' in captured.out
    assert '"cli_name": "codex"' in captured.out


def test_docs_agent_factory_example_matches_supported_agent_names():
    assert AgentCtrl.make("codex").capabilities().agent_type is AgentType.CODEX
    assert AgentCtrl.make(AgentType.GEMINI).capabilities().agent_type is AgentType.GEMINI


def test_docs_builder_examples_are_valid_without_live_execution():
    codex = AgentCtrl.codex().with_sandbox("workspace-write")
    opencode = AgentCtrl.open_code().with_agent("coder")
    pi = AgentCtrl.pi().with_thinking("high")
    gemini = AgentCtrl.gemini().plan_mode()

    assert codex._request.provider_options["sandbox"] == "workspace-write"
    assert opencode._request.provider_options["agent"] == "coder"
    assert pi._request.provider_options["thinking"] == "high"
    assert gemini._request.provider_options["approval_mode"] == "plan"


def test_user_cli_supported_agents_match_actual_cli_output(capsys):
    main(["agents", "list"])
    actual_agents = capsys.readouterr().out.splitlines()

    cli_doc = (REPO_ROOT / "docs/user/cli.md").read_text(encoding="utf-8")

    for agent in actual_agents:
        assert f"- `{agent}`" in cli_doc


def test_live_examples_are_labeled_in_public_docs():
    docs = {
        "README.md": (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
        "docs/user/quickstart.md": (REPO_ROOT / "docs/user/quickstart.md").read_text(encoding="utf-8"),
        "docs/user/cli.md": (REPO_ROOT / "docs/user/cli.md").read_text(encoding="utf-8"),
    }

    for path, text in docs.items():
        assert "installed and authenticated" in text, path
