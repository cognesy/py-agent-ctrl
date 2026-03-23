import os
from pathlib import Path


def install_fake_cli(tmp_path: Path, name: str, lines: list[str]) -> None:
    script = tmp_path / name
    payload = "\n".join(f"printf '%s\\n' '{line}'" for line in lines)
    script.write_text(f"#!/bin/sh\n{payload}\n", encoding="utf-8")
    script.chmod(0o755)


def prepend_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
