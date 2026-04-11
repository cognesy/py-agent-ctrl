from __future__ import annotations

from py_agent_ctrl.actions.base import BaseAgentAction
from py_agent_ctrl.api.events import StreamResult
from py_agent_ctrl.api.models import (
    AgentRequest,
    AgentResponse,
    AgentType,
    BridgeCapabilities,
    ClaudePermissionMode,
    CodexSandboxMode,
    GeminiApprovalMode,
)
from py_agent_ctrl.services.bridges.claude_code.bridge import ClaudeCodeBridge
from py_agent_ctrl.services.bridges.codex.bridge import CodexBridge
from py_agent_ctrl.services.bridges.gemini.bridge import GeminiBridge
from py_agent_ctrl.services.bridges.opencode.bridge import OpenCodeBridge
from py_agent_ctrl.services.bridges.pi.bridge import PiBridge


class ClaudeCodeAction(BaseAgentAction):
    def with_permission_mode(self, mode: ClaudePermissionMode | str) -> ClaudeCodeAction:
        return self._with_provider_option("permission_mode", ClaudePermissionMode(mode).value)

    def with_allowed_tools(self, *tools: str) -> ClaudeCodeAction:
        return self._with_provider_option("allowed_tools", list(tools))


class CodexAction(BaseAgentAction):
    def with_sandbox(self, mode: CodexSandboxMode | str) -> CodexAction:
        return self._with_provider_option("sandbox", CodexSandboxMode(mode).value)

    def disable_sandbox(self) -> CodexAction:
        return self.with_sandbox("danger-full-access")

    def full_auto(self, enabled: bool = True) -> CodexAction:
        return self._with_provider_option("full_auto", enabled)

    def dangerously_bypass(self, enabled: bool = True) -> CodexAction:
        return self._with_provider_option("dangerously_bypass", enabled)

    def skip_git_repo_check(self, enabled: bool = True) -> CodexAction:
        return self._with_provider_option("skip_git_repo_check", enabled)

    def with_images(self, images: list[str]) -> CodexAction:
        return self._with_provider_option("images", list(images))


class OpenCodeAction(BaseAgentAction):
    def with_agent(self, agent: str) -> OpenCodeAction:
        return self._with_provider_option("agent", agent)

    def with_files(self, files: list[str]) -> OpenCodeAction:
        return self._with_provider_option("files", list(files))

    def with_title(self, title: str) -> OpenCodeAction:
        return self._with_provider_option("title", title)

    def share_session(self, enabled: bool = True) -> OpenCodeAction:
        return self._with_provider_option("share_session", enabled)


class PiAction(BaseAgentAction):
    def with_provider(self, provider: str) -> PiAction:
        return self._with_provider_option("provider", provider)

    def with_thinking(self, level: str) -> PiAction:
        return self._with_provider_option("thinking", level)

    def with_tools(self, tools: list[str]) -> PiAction:
        return self._with_provider_option("tools", list(tools))

    def no_tools(self) -> PiAction:
        return self._with_provider_option("no_tools", True)

    def with_files(self, files: list[str]) -> PiAction:
        return self._with_provider_option("files", list(files))

    def with_extensions(self, extensions: list[str]) -> PiAction:
        return self._with_provider_option("extensions", list(extensions))

    def no_extensions(self) -> PiAction:
        return self._with_provider_option("no_extensions", True)

    def with_skills(self, skills: list[str]) -> PiAction:
        return self._with_provider_option("skills", list(skills))

    def no_skills(self) -> PiAction:
        return self._with_provider_option("no_skills", True)

    def ephemeral(self) -> PiAction:
        return self._with_provider_option("no_session", True)

    def with_session_dir(self, session_dir: str) -> PiAction:
        return self._with_provider_option("session_dir", session_dir)

    def with_api_key(self, api_key: str) -> PiAction:
        return self._with_provider_option("api_key", api_key)


class GeminiAction(BaseAgentAction):
    def with_approval_mode(self, mode: GeminiApprovalMode | str) -> GeminiAction:
        return self._with_provider_option("approval_mode", GeminiApprovalMode(mode).value)

    def yolo(self) -> GeminiAction:
        return self.with_approval_mode("yolo")

    def plan_mode(self) -> GeminiAction:
        return self.with_approval_mode("plan")

    def with_sandbox(self, enabled: bool = True) -> GeminiAction:
        return self._with_provider_option("sandbox", enabled)

    def with_include_directories(self, directories: list[str]) -> GeminiAction:
        return self._with_provider_option("include_directories", list(directories))

    def with_extensions(self, extensions: list[str]) -> GeminiAction:
        return self._with_provider_option("extensions", list(extensions))

    def with_allowed_tools(self, tools: list[str]) -> GeminiAction:
        return self._with_provider_option("allowed_tools", list(tools))

    def with_allowed_mcp_servers(self, servers: list[str]) -> GeminiAction:
        return self._with_provider_option("allowed_mcp_servers", list(servers))

    def with_policy(self, policy_files: list[str]) -> GeminiAction:
        return self._with_provider_option("policy_files", list(policy_files))

    def debug(self) -> GeminiAction:
        return self._with_provider_option("debug", True)


class PlaceholderBridge:
    def __init__(self, agent_type: AgentType, cli_name: str) -> None:
        self._agent_type = agent_type
        self._cli_name = cli_name

    def capabilities(self) -> BridgeCapabilities:
        return BridgeCapabilities(
            agent_type=self._agent_type,
            cli_name=self._cli_name,
            supported_options=[],
        )

    def execute(self, request: AgentRequest) -> AgentResponse:
        raise NotImplementedError(f"{self._agent_type.value} bridge is not implemented yet")

    def stream(self, request: AgentRequest) -> StreamResult:
        raise NotImplementedError(f"{self._agent_type.value} bridge is not implemented yet")


def make_claude_code_action() -> ClaudeCodeAction:
    return ClaudeCodeAction(ClaudeCodeBridge())


def make_codex_action() -> CodexAction:
    return CodexAction(CodexBridge())


def make_opencode_action() -> OpenCodeAction:
    return OpenCodeAction(OpenCodeBridge())


def make_pi_action() -> PiAction:
    return PiAction(PiBridge())


def make_gemini_action() -> GeminiAction:
    return GeminiAction(GeminiBridge())
