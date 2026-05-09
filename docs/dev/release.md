# Release Readiness

Use this checklist before publishing, tagging, or treating a git revision as
release-ready. It is a manual local gate for this git repository; it is not a
scheduled CI/CD workflow.

## Required Gate

Run the required checks from a clean checkout state:

```bash
uv sync --extra dev
uv run python -m ruff format --check .
uv run python -m ruff check .
uv run python -m mypy libs/py_agent_ctrl apps
uv run python -m pytest -q -m "not live"
uv run python -m pytest -m "not live" --cov=py_agent_ctrl --cov-report=term-missing
uv run python -m pytest -q tests/feature/test_docs_examples.py tests/feature/test_ctrlagent_cli.py
uv run python -m compileall -q apps libs tests
uv build
uvx twine check dist/*
uv export --format requirements.txt --extra dev --no-hashes --no-emit-project --locked | uvx pip-audit --no-deps --disable-pip -r /dev/stdin
```

## Clean Install Smoke

After `uv build`, install the built wheel into an isolated environment and
verify the import surface, `py.typed`, and the `ctrlagent` console entrypoint:

```bash
wheel="$(find dist -name 'py_agent_ctrl-*.whl' -type f | head -n 1)"
uv run --isolated --with "$wheel" python -c "import py_agent_ctrl; print(py_agent_ctrl.__name__)"
uv run --isolated --with "$wheel" python -c "import importlib.resources as r; assert r.files('py_agent_ctrl').joinpath('py.typed').is_file(); print('py.typed')"
uv run --isolated --with "$wheel" ctrlagent agents list
```

## Optional Live-Agent Confidence Check

Live-agent e2e is manual-only and provider-scoped. It is not a default release
blocker unless the release owner explicitly chooses to include it for a given
release. The selected provider CLI must be installed and authenticated first.

Run one provider:

```bash
PY_AGENT_CTRL_RUN_LIVE_INTEGRATION=1 PY_AGENT_CTRL_LIVE_AGENTS=codex uv run python -m pytest -q tests/integration -m live
```

Run all configured providers:

```bash
PY_AGENT_CTRL_RUN_LIVE_INTEGRATION=1 uv run python -m pytest -q tests/integration -m live
```

Record skipped live-agent checks with the reason, such as intentionally avoiding
credentialed external-agent usage, missing local provider credentials, or a
missing provider CLI.

## Before Push

After all checks pass, confirm only intended files are staged or committed:

```bash
git status --short
```
