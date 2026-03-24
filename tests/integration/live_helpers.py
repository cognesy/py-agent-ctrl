from __future__ import annotations

import json
import os
import shutil

import pytest

LIVE_AGENT_ENV = "PY_AGENT_CTRL_RUN_LIVE_INTEGRATION"
LIVE_AGENTS_ENV = "PY_AGENT_CTRL_LIVE_AGENTS"
LIVE_TEST_PROMPT = (
    'List directory names directly under ~/projects. '
    'Return only valid JSON in the exact shape {"directories":["name1","name2"]}. '
    "Do not include markdown fences or any explanatory text."
)


def require_live_agent(agent_name: str, cli_name: str) -> None:
    if os.environ.get(LIVE_AGENT_ENV) != "1":
        pytest.skip(f"set {LIVE_AGENT_ENV}=1 to run live integration tests")

    enabled_agents = {
        item.strip()
        for item in os.environ.get(LIVE_AGENTS_ENV, "").split(",")
        if item.strip()
    }
    if enabled_agents and agent_name not in enabled_agents:
        pytest.skip(f"{agent_name} not enabled in {LIVE_AGENTS_ENV}")

    if shutil.which(cli_name) is None:
        pytest.skip(f"{cli_name} is not installed on PATH")


def _extract_json_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1]).strip()
    return stripped


def assert_live_response(response) -> dict[str, object]:
    assert response.exit_code == 0
    assert response.text
    payload = json.loads(_extract_json_text(response.text))
    assert isinstance(payload, dict)
    directories = payload.get("directories")
    assert isinstance(directories, list)
    assert all(isinstance(item, str) for item in directories)
    assert "py-agent-ctrl" in directories
    return payload
