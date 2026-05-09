# Quality Commands

This repository uses `uv` only for dependency management, execution, linting,
and tests. Do not add a `Makefile`, `justfile`, or wrapper script for the first
QA hardening pass.

## Local Baseline

Run these before committing changes:

```bash
uv sync --extra dev
uv run python -m ruff check .
uv run python -m mypy libs/py_agent_ctrl
uv run python -m pytest -q
uv run python -m compileall -q apps libs tests
uv build --wheel
```

Use module invocation for Python tools (`uv run python -m ...`) instead of
direct console scripts such as `uv run pytest` or `uv run mypy`. A reused
virtualenv can contain stale console-script shebangs after the checkout path is
moved or renamed, while module invocation uses the active interpreter from the
current environment.

## CLI Smoke

For the editable checkout, run:

```bash
uv run python -m py_agent_ctrl.cli agents list
```

Later QA hardening tasks will add a clean wheel install smoke test for the
installed `ctrlagent` entrypoint.
