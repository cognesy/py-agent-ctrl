import subprocess

from py_agent_ctrl.services.core.subprocess import run_process


def test_run_process_returns_process_output_on_success(tmp_path):
    script = tmp_path / "ok.sh"
    script.write_text("#!/bin/sh\necho hello\n", encoding="utf-8")
    script.chmod(0o755)

    import os
    output = run_process([str(script)], cwd=None, env=dict(os.environ), timeout_seconds=10)

    assert output.exit_code == 0
    assert "hello" in output.stdout


def test_run_process_catches_timeout_and_returns_error_output(monkeypatch):
    def _raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["sleep", "99"], timeout=1)

    monkeypatch.setattr("py_agent_ctrl.services.core.subprocess.subprocess.run", _raise_timeout)

    import os
    output = run_process(["sleep", "99"], cwd=None, env=dict(os.environ), timeout_seconds=1)

    assert output.exit_code == -1
    assert output.stdout == ""
    assert "timed out" in output.stderr.lower()
