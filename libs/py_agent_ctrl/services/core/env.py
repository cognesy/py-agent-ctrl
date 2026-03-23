from __future__ import annotations

import os


def cleaned_agent_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("CLAUDECODE") or key.startswith("CLAUDE_CODE"):
            del env[key]
    return env
