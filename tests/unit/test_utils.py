import os

from py_agent_ctrl.actions.sessions import with_continue, with_resume
from py_agent_ctrl.api.models import AgentRequest
from py_agent_ctrl.services.core.env import cleaned_agent_env

# ── cleaned_agent_env ──────────────────────────────────────────────────────


def test_cleaned_agent_env_strips_claude_code_vars(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_FOO", "should-be-removed")
    monkeypatch.setenv("CLAUDECODE_BAR", "also-removed")

    result = cleaned_agent_env()

    assert "CLAUDE_CODE_FOO" not in result
    assert "CLAUDECODE_BAR" not in result


def test_cleaned_agent_env_keeps_unrelated_vars(monkeypatch):
    monkeypatch.setenv("MY_APP_VAR", "keep-me")

    result = cleaned_agent_env()

    assert result["MY_APP_VAR"] == "keep-me"


def test_cleaned_agent_env_does_not_mutate_os_environ(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SECRET", "secret")

    cleaned_agent_env()

    assert os.environ.get("CLAUDE_CODE_SECRET") == "secret"


# ── sessions helpers ───────────────────────────────────────────────────────


def test_with_resume_sets_session_id_and_clears_continue():
    request = AgentRequest(prompt="x", continue_session=True)

    result = with_resume(request, "abc-123")

    assert result.resume_session_id == "abc-123"
    assert result.continue_session is False


def test_with_resume_does_not_mutate_original():
    request = AgentRequest(prompt="x", continue_session=True)

    with_resume(request, "abc-123")

    assert request.resume_session_id is None
    assert request.continue_session is True


def test_with_continue_sets_flag_and_clears_session_id():
    request = AgentRequest(prompt="x", resume_session_id="old-session")

    result = with_continue(request)

    assert result.continue_session is True
    assert result.resume_session_id is None


def test_with_continue_does_not_mutate_original():
    request = AgentRequest(prompt="x", resume_session_id="old-session")

    with_continue(request)

    assert request.resume_session_id == "old-session"
    assert request.continue_session is False
