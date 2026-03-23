from __future__ import annotations

import shutil

from py_agent_ctrl.services.core.errors import BinaryNotFoundError


def require_binary(binary_name: str, install_hint: str) -> str:
    binary = shutil.which(binary_name)
    if binary is None:
        raise BinaryNotFoundError(binary_name, install_hint)
    return binary
