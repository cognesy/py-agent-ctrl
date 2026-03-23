from __future__ import annotations

import json
import subprocess
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass


@dataclass(slots=True)
class ProcessOutput:
    exit_code: int
    stdout: str
    stderr: str


def run_process(
    argv: list[str],
    *,
    cwd: str | None,
    env: dict[str, str],
    timeout_seconds: int,
) -> ProcessOutput:
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=cwd,
            env=env,
        )
    except subprocess.TimeoutExpired:
        # subprocess.run kills the process internally before re-raising
        return ProcessOutput(
            exit_code=-1,
            stdout="",
            stderr=f"Process timed out after {timeout_seconds}s",
        )
    return ProcessOutput(
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def stream_process(
    argv: list[str],
    *,
    cwd: str | None,
    env: dict[str, str],
    timeout_seconds: int,
) -> tuple[Iterator[tuple[dict[str, object] | None, str]], Callable[[], int]]:
    exit_code: list[int] = [0]

    def _generate() -> Iterator[tuple[dict[str, object] | None, str]]:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=cwd,
            env=env,
        )
        watchdog = threading.Timer(timeout_seconds, proc.kill)
        watchdog.daemon = True
        watchdog.start()
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    yield json.loads(stripped), stripped
                except json.JSONDecodeError:
                    yield None, stripped
        finally:
            watchdog.cancel()
            if proc.stdout:
                proc.stdout.close()
            proc.wait()
            exit_code[0] = proc.returncode

    return _generate(), lambda: exit_code[0]


def iter_json_lines(stdout: str) -> Iterator[tuple[dict[str, object] | None, str]]:
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            yield json.loads(stripped), stripped
        except json.JSONDecodeError:
            yield None, stripped
