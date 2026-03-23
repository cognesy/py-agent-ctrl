from __future__ import annotations


class AgentError(RuntimeError):
    pass


class BinaryNotFoundError(AgentError):
    def __init__(self, binary_name: str, install_hint: str) -> None:
        super().__init__(f"{binary_name} CLI not found on PATH. {install_hint}")
        self.binary_name = binary_name
        self.install_hint = install_hint
