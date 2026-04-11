import pytest
from py_agent_ctrl import (
    AgentCtrl,
    ClaudeCodeProviderOptions,
    ClaudePermissionMode,
    CodexProviderOptions,
    CodexSandboxMode,
    GeminiApprovalMode,
    GeminiProviderOptions,
    SandboxDriver,
)
from py_agent_ctrl.actions.agents import (
    ClaudeCodeAction,
    CodexAction,
    GeminiAction,
    OpenCodeAction,
    PiAction,
)
from pydantic import ValidationError

# --- type preservation ---

def test_claude_builder_chain_returns_claude_code_action():
    action = AgentCtrl.claude_code().with_model("x").with_permission_mode("bypassPermissions")
    assert isinstance(action, ClaudeCodeAction)


def test_codex_builder_chain_returns_codex_action():
    action = AgentCtrl.codex().with_model("o4-mini").with_sandbox("workspace-write")
    assert isinstance(action, CodexAction)


def test_opencode_builder_chain_returns_opencode_action():
    action = AgentCtrl.opencode().with_model("claude-sonnet").with_agent("coder")
    assert isinstance(action, OpenCodeAction)


def test_pi_builder_chain_returns_pi_action():
    action = AgentCtrl.pi().with_model("sonnet").with_thinking("high")
    assert isinstance(action, PiAction)


def test_gemini_builder_chain_returns_gemini_action():
    action = AgentCtrl.gemini().with_model("flash").yolo()
    assert isinstance(action, GeminiAction)


# --- provider_options accumulation ---

def test_claude_provider_options_accumulate():
    action = (
        AgentCtrl.claude_code()
        .with_permission_mode(ClaudePermissionMode.BYPASS_PERMISSIONS)
        .with_allowed_tools("Read", "Edit")
    )
    opts = action._request.provider_options
    assert opts["permission_mode"] == "bypassPermissions"
    assert opts["allowed_tools"] == ["Read", "Edit"]


def test_codex_provider_options_accumulate():
    action = (
        AgentCtrl.codex()
        .with_sandbox(CodexSandboxMode.WORKSPACE_WRITE)
        .full_auto()
        .skip_git_repo_check()
    )
    opts = action._request.provider_options
    assert opts["sandbox"] == "workspace-write"
    assert opts["full_auto"] is True
    assert opts["skip_git_repo_check"] is True


def test_gemini_provider_options_accumulate():
    action = (
        AgentCtrl.gemini()
        .with_approval_mode(GeminiApprovalMode.PLAN)
        .with_sandbox()
        .with_allowed_tools(["read_file"])
    )
    opts = action._request.provider_options
    assert opts["approval_mode"] == "plan"
    assert opts["sandbox"] is True
    assert opts["allowed_tools"] == ["read_file"]


# --- base builder fields ---

def test_with_model_sets_model():
    action = AgentCtrl.claude_code().with_model("claude-opus")
    assert action._request.model == "claude-opus"


def test_with_timeout_sets_timeout():
    action = AgentCtrl.claude_code().with_timeout(300)
    assert action._request.timeout_seconds == 300


def test_with_sandbox_driver_sets_typed_driver():
    action = AgentCtrl.codex().with_sandbox_driver("docker")
    assert action._request.sandbox_driver == SandboxDriver.DOCKER


def test_in_directory_sets_working_directory():
    action = AgentCtrl.claude_code().in_directory("/tmp/work")
    assert action._request.working_directory == "/tmp/work"


def test_with_max_turns_clamps_to_minimum_one():
    action = AgentCtrl.claude_code().with_max_turns(0)
    assert action._request.max_turns == 1


def test_resume_session_sets_id_and_clears_continue():
    action = AgentCtrl.claude_code().resume_session("abc-123")
    assert action._request.resume_session_id == "abc-123"
    assert action._request.continue_session is False


def test_continue_session_sets_flag_and_clears_resume():
    action = AgentCtrl.claude_code().resume_session("abc").continue_session()
    assert action._request.continue_session is True
    assert action._request.resume_session_id is None


def test_builder_is_immutable_original_unchanged():
    base = AgentCtrl.claude_code()
    modified = base.with_model("new-model")
    assert base._request.model is None
    assert modified._request.model == "new-model"


def test_invalid_provider_modes_fail_early():
    with pytest.raises(ValueError):
        AgentCtrl.claude_code().with_permission_mode("not-a-mode")
    with pytest.raises(ValueError):
        AgentCtrl.codex().with_sandbox("not-a-sandbox")
    with pytest.raises(ValueError):
        AgentCtrl.gemini().with_approval_mode("not-an-approval-mode")


def test_provider_option_models_validate_known_modes():
    claude = ClaudeCodeProviderOptions(permission_mode="bypassPermissions", allowed_tools=["Read"])
    codex = CodexProviderOptions(sandbox="workspace-write", full_auto=True)
    gemini = GeminiProviderOptions(approval_mode="plan", sandbox=True)

    assert claude.permission_mode == ClaudePermissionMode.BYPASS_PERMISSIONS
    assert codex.sandbox == CodexSandboxMode.WORKSPACE_WRITE
    assert gemini.approval_mode == GeminiApprovalMode.PLAN


def test_provider_option_models_reject_invalid_modes():
    with pytest.raises(ValidationError):
        ClaudeCodeProviderOptions(permission_mode="bad")
    with pytest.raises(ValidationError):
        CodexProviderOptions(sandbox="bad")
    with pytest.raises(ValidationError):
        GeminiProviderOptions(approval_mode="bad")
