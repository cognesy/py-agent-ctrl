import subprocess
from collections.abc import Callable, Iterator

from py_agent_ctrl.services.core.subprocess import (
    CommandSpec,
    HostCommandExecutor,
    JsonLinesParser,
    ProcessOutput,
    iter_json_lines,
    run_process,
    stream_process,
    tail_text,
)


def test_run_process_returns_process_output_on_success(tmp_path):
    script = tmp_path / "ok.sh"
    script.write_text("#!/bin/sh\necho hello\n", encoding="utf-8")
    script.chmod(0o755)

    import os
    output = run_process([str(script)], cwd=None, env=dict(os.environ), timeout_seconds=10)

    assert output.exit_code == 0
    assert "hello" in output.stdout
    assert output.error_type is None
    assert output.command_preview == [str(script)]
    assert output.duration_ms is not None


def test_run_process_catches_timeout_and_returns_error_output(monkeypatch):
    def _raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["sleep", "99"], timeout=1)

    monkeypatch.setattr("py_agent_ctrl.services.core.subprocess.subprocess.run", _raise_timeout)

    import os
    output = run_process(["sleep", "99"], cwd=None, env=dict(os.environ), timeout_seconds=1)

    assert output.exit_code == -1
    assert output.stdout == ""
    assert "timed out" in output.stderr.lower()
    assert output.timed_out is True
    assert output.error_type == "timeout"


def test_run_process_reports_missing_working_directory(tmp_path):
    import os

    missing = tmp_path / "missing"
    output = run_process(["echo", "hello"], cwd=str(missing), env=dict(os.environ), timeout_seconds=1)

    assert output.exit_code == 1
    assert output.error_type == "working_directory_not_found"
    assert output.cwd == str(missing)
    assert "working directory" in output.stderr.lower()


def test_run_process_reports_process_start_failure(monkeypatch):
    def _raise_os_error(*args, **kwargs):
        raise OSError("cannot start")

    monkeypatch.setattr("py_agent_ctrl.services.core.subprocess.subprocess.run", _raise_os_error)

    import os

    output = run_process(["agent"], cwd=None, env=dict(os.environ), timeout_seconds=1)

    assert output.exit_code == 1
    assert output.error_type == "process_start_failed"
    assert output.stderr_tail == "cannot start"


def test_run_process_records_nonzero_failure_diagnostics(tmp_path):
    script = tmp_path / "fail.sh"
    script.write_text("#!/bin/sh\necho 'bad stderr' >&2\nexit 7\n", encoding="utf-8")
    script.chmod(0o755)

    import os

    output = run_process([str(script)], cwd=None, env=dict(os.environ), timeout_seconds=10)

    assert output.exit_code == 7
    assert output.error_type == "process_failed"
    assert output.stderr_tail.strip() == "bad stderr"
    assert output.command_preview == [str(script)]


def test_tail_text_returns_bounded_suffix():
    assert tail_text("abcdef", max_chars=3) == "def"


def test_host_command_executor_accepts_stdin(tmp_path):
    script = tmp_path / "stdin.py"
    script.write_text(
        "import sys\nprint(sys.stdin.read().upper())\n",
        encoding="utf-8",
    )

    import os

    output = HostCommandExecutor().run(
        CommandSpec(
            argv=["python", str(script)],
            cwd=None,
            env=dict(os.environ),
            stdin="hello",
            timeout_seconds=10,
        )
    )

    assert output.exit_code == 0
    assert output.stdout.strip() == "HELLO"


class FakeExecutor:
    def __init__(self) -> None:
        self.commands: list[CommandSpec] = []

    def run(self, command: CommandSpec) -> ProcessOutput:
        self.commands.append(command)
        return ProcessOutput(exit_code=0, stdout="ok", stderr="")

    def stream_lines(self, command: CommandSpec) -> tuple[Iterator[str], Callable[[], int]]:
        self.commands.append(command)
        return iter(['{"type":"ok"}', "not-json"]), lambda: 3


def test_run_process_delegates_to_executor():
    executor = FakeExecutor()

    output = run_process(
        ["agent", "run"],
        cwd="/tmp/work",
        env={"PATH": "/tmp/bin"},
        timeout_seconds=5,
        stdin="prompt",
        executor=executor,
    )

    assert output.stdout == "ok"
    assert executor.commands == [
        CommandSpec(
            argv=["agent", "run"],
            cwd="/tmp/work",
            env={"PATH": "/tmp/bin"},
            timeout_seconds=5,
            stdin="prompt",
        )
    ]


def test_stream_process_delegates_to_executor_and_parses_json_lines():
    executor = FakeExecutor()

    gen, get_exit_code = stream_process(
        ["agent", "stream"],
        cwd="/tmp/work",
        env={"PATH": "/tmp/bin"},
        timeout_seconds=5,
        stdin="prompt",
        executor=executor,
    )

    assert list(gen) == [({"type": "ok"}, '{"type":"ok"}'), (None, "not-json")]
    assert get_exit_code() == 3
    assert executor.commands[0].argv == ["agent", "stream"]
    assert executor.commands[0].stdin == "prompt"


def test_json_lines_parser_buffers_chunked_lines():
    parser = JsonLinesParser()

    first = list(parser.consume('{"type"'))
    second = list(parser.consume(':"ok"}\n{"type":"next"}'))
    final = list(parser.finish())

    assert first == []
    assert [line.payload for line in second + final] == [{"type": "ok"}, {"type": "next"}]
    assert parser.diagnostics.parse_failures == 0


def test_json_lines_parser_records_bounded_failure_samples():
    parser = JsonLinesParser(sample_limit=2)

    lines = list(parser.consume("not-json-1\nnot-json-2\nnot-json-3\n"))

    assert [line.payload for line in lines] == [None, None, None]
    assert parser.diagnostics.parse_failures == 3
    assert parser.diagnostics.skipped_non_json_lines == 3
    assert parser.diagnostics.parse_failure_samples == ["not-json-1", "not-json-2"]


def test_json_lines_parser_tracks_overlong_lines():
    parser = JsonLinesParser(max_line_bytes=5)

    lines = list(parser.consume('{"toolong":true}\n'))

    assert len(lines) == 1
    assert lines[0].payload is None
    assert lines[0].error == "line exceeded maximum size"
    assert parser.diagnostics.parse_failures == 1
    assert parser.diagnostics.overlong_lines == 1


def test_iter_json_lines_uses_shared_parser_for_non_object_json():
    assert list(iter_json_lines('[1, 2]\n{"type":"ok"}\n')) == [
        (None, "[1, 2]"),
        ({"type": "ok"}, '{"type":"ok"}'),
    ]
