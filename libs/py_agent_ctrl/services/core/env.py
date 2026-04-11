from __future__ import annotations

import os
from collections.abc import Mapping

from py_agent_ctrl.api.models import AgentType

SENSITIVE_ENV_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD")


def cleaned_agent_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("CLAUDECODE") or key.startswith("CLAUDE_CODE"):
            del env[key]
    return env


def mask_sensitive_value(key: str, value: object) -> str:
    text = str(value)
    key_upper = key.upper()
    if not any(marker in key_upper for marker in SENSITIVE_ENV_MARKERS):
        return text
    if not text:
        return ""
    if len(text) <= 8:
        return "****"
    return f"{text[:4]}****{text[-4:]}"


def provider_env_overrides(
    agent_type: AgentType,
    provider_options: Mapping[str, object] | None = None,
) -> dict[str, str]:
    options = provider_options or {}
    env: dict[str, str] = {}
    api_key = options.get("api_key")
    base_url = options.get("base_url")

    if agent_type is AgentType.CLAUDE_CODE:
        if api_key:
            env["ANTHROPIC_API_KEY"] = str(api_key)
        if base_url:
            env["ANTHROPIC_BASE_URL"] = str(base_url)
    elif agent_type is AgentType.CODEX:
        if api_key:
            env["OPENAI_API_KEY"] = str(api_key)
        if base_url:
            env["OPENAI_BASE_URL"] = str(base_url)
    elif agent_type is AgentType.GEMINI:
        if api_key:
            env["GEMINI_API_KEY"] = str(api_key)
            env.setdefault("GEMINI_API_KEY_AUTH_MECHANISM", "bearer")
        if base_url:
            env["GOOGLE_GEMINI_BASE_URL"] = str(base_url)

    return env


def agent_env(
    agent_type: AgentType,
    provider_options: Mapping[str, object] | None = None,
) -> dict[str, str]:
    env = cleaned_agent_env()
    env.update(provider_env_overrides(agent_type, provider_options))
    return env
