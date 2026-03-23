from __future__ import annotations

from py_agent_ctrl.actions.agents import (
    ClaudeCodeAction,
    CodexAction,
    GeminiAction,
    OpenCodeAction,
    PiAction,
    make_claude_code_action,
    make_codex_action,
    make_gemini_action,
    make_opencode_action,
    make_pi_action,
)


class AgentCtrl:
    @staticmethod
    def claude_code() -> ClaudeCodeAction:
        return make_claude_code_action()

    @staticmethod
    def codex() -> CodexAction:
        return make_codex_action()

    @staticmethod
    def opencode() -> OpenCodeAction:
        return make_opencode_action()

    @staticmethod
    def pi() -> PiAction:
        return make_pi_action()

    @staticmethod
    def gemini() -> GeminiAction:
        return make_gemini_action()
