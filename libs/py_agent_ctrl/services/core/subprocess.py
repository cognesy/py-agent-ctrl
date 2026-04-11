from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Protocol

DEFAULT_JSON_LINE_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_PARSE_FAILURE_SAMPLE_LIMIT = 5
DEFAULT_STDERR_TAIL_CHARS = 4096


@dataclass(frozen=True, slots=True)
class CommandSpec:
    argv: list[str]
    cwd: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: int = 120
    stdin: str | None = None
    execution_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ProcessOutput:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    stderr_tail: str = ""
    duration_ms: int | None = None
    command_preview: list[str] = field(default_factory=list)
    cwd: str | None = None
    error_type: str | None = None


@dataclass(slots=True)
class JsonLine:
    payload: dict[str, object] | None
    raw_line: str
    error: str | None = None


@dataclass(slots=True)
class JsonParseDiagnostics:
    parse_failures: int = 0
    skipped_non_json_lines: int = 0
    overlong_lines: int = 0
    parse_failure_samples: list[str] = field(default_factory=list)


class JsonLinesParser:
    def __init__(
        self,
        *,
        max_line_bytes: int = DEFAULT_JSON_LINE_MAX_BYTES,
        sample_limit: int = DEFAULT_PARSE_FAILURE_SAMPLE_LIMIT,
    ) -> None:
        self.max_line_bytes = max_line_bytes
        self.sample_limit = sample_limit
        self.diagnostics = JsonParseDiagnostics()
        self._tail = ""

    def consume(self, chunk: str) -> Iterator[JsonLine]:
        self._tail += chunk
        while True:
            newline_index = self._tail.find("\n")
            if newline_index < 0:
                break
            raw_line = self._tail[:newline_index].rstrip("\r")
            self._tail = self._tail[newline_index + 1 :]
            parsed = self.parse_line(raw_line)
            if parsed is not None:
                yield parsed

    def finish(self) -> Iterator[JsonLine]:
        if not self._tail:
            return
        raw_line = self._tail.rstrip("\r")
        self._tail = ""
        parsed = self.parse_line(raw_line)
        if parsed is not None:
            yield parsed

    def parse_line(self, raw_line: str) -> JsonLine | None:
        stripped = raw_line.strip()
        if not stripped:
            return None
        if len(stripped.encode("utf-8")) > self.max_line_bytes:
            self._record_failure(stripped, "line exceeded maximum size")
            self.diagnostics.overlong_lines += 1
            return JsonLine(payload=None, raw_line=stripped, error="line exceeded maximum size")
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as error:
            self._record_failure(stripped, str(error))
            self.diagnostics.skipped_non_json_lines += 1
            return JsonLine(payload=None, raw_line=stripped, error=str(error))
        if not isinstance(payload, dict):
            type_error = f"JSON payload is not an object: {type(payload).__name__}"
            self._record_failure(stripped, type_error)
            return JsonLine(payload=None, raw_line=stripped, error=type_error)
        return JsonLine(payload=payload, raw_line=stripped)

    def _record_failure(self, raw_line: str, _error: str) -> None:
        self.diagnostics.parse_failures += 1
        if len(self.diagnostics.parse_failure_samples) < self.sample_limit:
            self.diagnostics.parse_failure_samples.append(raw_line)


class CommandExecutor(Protocol):
    def run(self, command: CommandSpec) -> ProcessOutput: ...

    def stream_lines(self, command: CommandSpec) -> tuple[Iterator[str], Callable[[], int]]: ...


class HostCommandExecutor:
    def run(self, command: CommandSpec) -> ProcessOutput:
        started = time.perf_counter()

        def _output(
            *,
            exit_code: int,
            stdout: str = "",
            stderr: str = "",
            timed_out: bool = False,
            error_type: str | None = None,
        ) -> ProcessOutput:
            return ProcessOutput(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                timed_out=timed_out,
                stderr_tail=tail_text(stderr),
                duration_ms=int((time.perf_counter() - started) * 1000),
                command_preview=command.argv[:5],
                cwd=command.cwd,
                error_type=error_type,
            )

        if command.cwd is not None and not os.path.isdir(command.cwd):
            return _output(
                exit_code=1,
                stderr=f"Working directory does not exist: {command.cwd}",
                error_type="working_directory_not_found",
            )
        try:
            completed = subprocess.run(
                command.argv,
                capture_output=True,
                text=True,
                input=command.stdin,
                timeout=command.timeout_seconds,
                cwd=command.cwd,
                env=dict(command.env),
            )
        except subprocess.TimeoutExpired:
            # subprocess.run kills the process internally before re-raising
            return _output(
                exit_code=-1,
                stderr=f"Process timed out after {command.timeout_seconds}s",
                timed_out=True,
                error_type="timeout",
            )
        except FileNotFoundError as error:
            return _output(
                exit_code=127,
                stderr=str(error),
                error_type="process_start_failed",
            )
        except OSError as error:
            return _output(
                exit_code=1,
                stderr=str(error),
                error_type="process_start_failed",
            )
        return _output(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            error_type="process_failed" if completed.returncode != 0 else None,
        )

    def stream_lines(self, command: CommandSpec) -> tuple[Iterator[str], Callable[[], int]]:
        exit_code: list[int] = [0]

        def _generate() -> Iterator[str]:
            proc = subprocess.Popen(
                command.argv,
                stdin=subprocess.PIPE if command.stdin is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                cwd=command.cwd,
                env=dict(command.env),
            )
            watchdog = threading.Timer(command.timeout_seconds, proc.kill)
            watchdog.daemon = True
            watchdog.start()
            try:
                if command.stdin is not None and proc.stdin is not None:
                    proc.stdin.write(command.stdin)
                    proc.stdin.close()
                assert proc.stdout is not None
                for line in proc.stdout:
                    stripped = line.strip()
                    if stripped:
                        yield stripped
            finally:
                watchdog.cancel()
                if proc.stdout:
                    proc.stdout.close()
                proc.wait()
                exit_code[0] = proc.returncode

        return _generate(), lambda: exit_code[0]


DEFAULT_COMMAND_EXECUTOR = HostCommandExecutor()


def tail_text(text: str, max_chars: int = DEFAULT_STDERR_TAIL_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def run_command(
    command: CommandSpec,
    *,
    executor: CommandExecutor = DEFAULT_COMMAND_EXECUTOR,
) -> ProcessOutput:
    return executor.run(command)


def run_process(
    argv: list[str],
    *,
    cwd: str | None,
    env: dict[str, str],
    timeout_seconds: int,
    stdin: str | None = None,
    executor: CommandExecutor = DEFAULT_COMMAND_EXECUTOR,
) -> ProcessOutput:
    return run_command(
        CommandSpec(
            argv=argv,
            cwd=cwd,
            env=env,
            timeout_seconds=timeout_seconds,
            stdin=stdin,
        ),
        executor=executor,
    )


def stream_command_json_lines(
    command: CommandSpec,
    *,
    executor: CommandExecutor = DEFAULT_COMMAND_EXECUTOR,
) -> tuple[Iterator[tuple[dict[str, object] | None, str]], Callable[[], int]]:
    lines, get_exit_code = executor.stream_lines(command)

    def _generate() -> Iterator[tuple[dict[str, object] | None, str]]:
        parser = JsonLinesParser()
        for line in lines:
            parsed = parser.parse_line(line)
            if parsed is not None:
                yield parsed.payload, parsed.raw_line

    return _generate(), get_exit_code


def stream_process(
    argv: list[str],
    *,
    cwd: str | None,
    env: dict[str, str],
    timeout_seconds: int,
    stdin: str | None = None,
    executor: CommandExecutor = DEFAULT_COMMAND_EXECUTOR,
) -> tuple[Iterator[tuple[dict[str, object] | None, str]], Callable[[], int]]:
    return stream_command_json_lines(
        CommandSpec(
            argv=argv,
            cwd=cwd,
            env=env,
            timeout_seconds=timeout_seconds,
            stdin=stdin,
        ),
        executor=executor,
    )


def iter_json_lines(stdout: str) -> Iterator[tuple[dict[str, object] | None, str]]:
    parser = JsonLinesParser()
    for line in parser.consume(stdout):
        yield line.payload, line.raw_line
    for line in parser.finish():
        yield line.payload, line.raw_line
