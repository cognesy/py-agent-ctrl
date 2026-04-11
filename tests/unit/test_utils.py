import os

from py_agent_ctrl.actions.sessions import (
    capabilities_from_bridge,
    require_session_operation,
    session_info_from_response,
    with_continue,
    with_resume,
)
from py_agent_ctrl.api.models import AgentRequest, AgentResponse, AgentType, BridgeCapabilities, SessionOperation
from py_agent_ctrl.services.core.binaries import require_binary
from py_agent_ctrl.services.core.env import agent_env, cleaned_agent_env, mask_sensitive_value, provider_env_overrides
from py_agent_ctrl.services.core.errors import (
    BinaryNotFoundError,
    JsonDecodeFailureError,
    ProcessFailedError,
    ProcessStartError,
    ProcessTimeoutError,
    ProviderParseFailureError,
    UnsupportedSessionOperationError,
    WorkingDirectoryNotFoundError,
)

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


def test_provider_env_overrides_maps_codex_api_settings():
    result = provider_env_overrides(
        AgentType.CODEX,
        {"api_key": "sk-test", "base_url": "https://api.example.test"},
    )

    assert result == {
        "OPENAI_API_KEY": "sk-test",
        "OPENAI_BASE_URL": "https://api.example.test",
    }


def test_provider_env_overrides_maps_gemini_api_settings():
    result = provider_env_overrides(
        AgentType.GEMINI,
        {"api_key": "gemini-key", "base_url": "https://gemini.example.test"},
    )

    assert result == {
        "GEMINI_API_KEY": "gemini-key",
        "GEMINI_API_KEY_AUTH_MECHANISM": "bearer",
        "GOOGLE_GEMINI_BASE_URL": "https://gemini.example.test",
    }


def test_agent_env_cleans_claude_vars_and_adds_provider_overrides(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_FOO", "bad")
    monkeypatch.setenv("KEEP_ME", "ok")

    result = agent_env(
        AgentType.CLAUDE_CODE,
        {"api_key": "anthropic-key", "base_url": "https://anthropic.example.test"},
    )

    assert "CLAUDECODE" not in result
    assert "CLAUDE_CODE_FOO" not in result
    assert result["KEEP_ME"] == "ok"
    assert result["ANTHROPIC_API_KEY"] == "anthropic-key"
    assert result["ANTHROPIC_BASE_URL"] == "https://anthropic.example.test"


def test_provider_env_overrides_leaves_unsupported_provider_empty():
    assert provider_env_overrides(AgentType.OPENCODE, {"api_key": "ignored"}) == {}
    assert provider_env_overrides(AgentType.PI, {"api_key": "still-cli-option"}) == {}


def test_mask_sensitive_value_masks_keys_tokens_and_secrets():
    assert mask_sensitive_value("OPENAI_API_KEY", "sk-1234567890") == "sk-1****7890"
    assert mask_sensitive_value("SESSION_TOKEN", "short") == "****"
    assert mask_sensitive_value("PUBLIC_BASE_URL", "https://example.test") == "https://example.test"


def test_require_binary_error_remains_actionable(monkeypatch):
    monkeypatch.setattr("py_agent_ctrl.services.core.binaries.shutil.which", lambda _name: None)

    try:
        require_binary("missing-agent", "Install it with the documented command.")
    except BinaryNotFoundError as error:
        assert error.binary_name == "missing-agent"
        assert error.install_hint == "Install it with the documented command."
        assert "missing-agent CLI not found on PATH" in str(error)
    else:
        raise AssertionError("expected BinaryNotFoundError")


def test_execution_error_taxonomy_messages_are_actionable():
    assert "Working directory" in str(WorkingDirectoryNotFoundError("/missing"))
    assert "cannot start" in str(ProcessStartError("cannot start"))
    assert "5s" in str(ProcessTimeoutError(5))
    assert "exit code 7" in str(ProcessFailedError(7, "bad stderr"))
    assert "Failed to decode JSON" in str(JsonDecodeFailureError("not-json"))
    assert "codex parse failure" in str(ProviderParseFailureError("codex", "bad item"))
    assert "session operation" in str(UnsupportedSessionOperationError("codex", "fork"))


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


def test_session_capabilities_from_bridge_preserves_resume_continue_flags():
    capabilities = capabilities_from_bridge(
        BridgeCapabilities(
            agent_type=AgentType.CODEX,
            cli_name="codex",
            supports_session_resume=True,
            supports_continue=False,
        )
    )

    assert capabilities.can_resume is True
    assert capabilities.can_continue is False
    assert capabilities.can_list is False


def test_require_session_operation_fails_for_unsupported_operation():
    capabilities = capabilities_from_bridge(
        BridgeCapabilities(agent_type=AgentType.CODEX, cli_name="codex", supports_session_resume=True)
    )

    require_session_operation(AgentType.CODEX, capabilities, SessionOperation.RESUME)
    try:
        require_session_operation(AgentType.CODEX, capabilities, SessionOperation.LIST)
    except UnsupportedSessionOperationError as error:
        assert error.agent_type == "codex"
        assert error.operation == "list"
    else:
        raise AssertionError("expected UnsupportedSessionOperationError")


def test_session_info_from_response_distinguishes_execution_id_from_provider_session_id():
    response = AgentResponse(
        agent_type=AgentType.CLAUDE_CODE,
        execution_id="exec-1",
        session_id="provider-session-1",
        raw_response=[{"type": "result"}],
    )

    info = session_info_from_response(response)

    assert info is not None
    assert info.execution_id == "exec-1"
    assert info.session_id == "provider-session-1"
    assert info.agent_type == AgentType.CLAUDE_CODE
    assert info.raw == [{"type": "result"}]


def test_session_info_from_response_returns_none_without_provider_session_id():
    response = AgentResponse(agent_type=AgentType.CLAUDE_CODE, execution_id="exec-1")

    assert session_info_from_response(response) is None
