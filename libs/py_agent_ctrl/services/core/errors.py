from __future__ import annotations


class AgentError(RuntimeError):
    pass


class AgentExecutionError(AgentError):
    pass


class BinaryNotFoundError(AgentError):
    def __init__(self, binary_name: str, install_hint: str) -> None:
        super().__init__(f"{binary_name} CLI not found on PATH. {install_hint}")
        self.binary_name = binary_name
        self.install_hint = install_hint


class WorkingDirectoryNotFoundError(AgentExecutionError):
    def __init__(self, cwd: str) -> None:
        super().__init__(f"Working directory does not exist: {cwd}")
        self.cwd = cwd


class ProcessStartError(AgentExecutionError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ProcessTimeoutError(AgentExecutionError):
    def __init__(self, timeout_seconds: int) -> None:
        super().__init__(f"Process timed out after {timeout_seconds}s")
        self.timeout_seconds = timeout_seconds


class ProcessFailedError(AgentExecutionError):
    def __init__(self, exit_code: int, stderr_tail: str = "") -> None:
        message = f"Process failed with exit code {exit_code}"
        if stderr_tail:
            message = f"{message}: {stderr_tail}"
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr_tail = stderr_tail


class JsonDecodeFailureError(AgentExecutionError):
    def __init__(self, sample: str) -> None:
        super().__init__(f"Failed to decode JSON line: {sample[:100]}")
        self.sample = sample


class ProviderParseFailureError(AgentExecutionError):
    def __init__(self, provider: str, message: str) -> None:
        super().__init__(f"{provider} parse failure: {message}")
        self.provider = provider


class UnsupportedSessionOperationError(AgentExecutionError):
    def __init__(self, agent_type: str, operation: str) -> None:
        super().__init__(f"{agent_type} does not support session operation: {operation}")
        self.agent_type = agent_type
        self.operation = operation
