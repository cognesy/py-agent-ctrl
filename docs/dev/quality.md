# Quality Commands

This repository uses `uv` only for dependency management, execution, linting,
and tests. Do not add a `Makefile`, `justfile`, or wrapper script for the first
QA hardening pass.

## Local Baseline

Run these before committing changes:

```bash
uv sync --extra dev
uv run python -m ruff format --check .
uv run python -m ruff check .
uv run python -m mypy libs/py_agent_ctrl apps
uv run python -m pytest -q -m "not live"
uv run python -m pytest -m "not live" --cov=py_agent_ctrl --cov-report=term-missing
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

For the built wheel, run an isolated install smoke:

```bash
uv build --wheel
wheel="$(find dist -name 'py_agent_ctrl-*.whl' -type f | head -n 1)"
uv run --isolated --with "$wheel" python -c "import py_agent_ctrl; print(py_agent_ctrl.__name__)"
uv run --isolated --with "$wheel" python -c "import importlib.resources as r; assert r.files('py_agent_ctrl').joinpath('py.typed').is_file()"
uv run --isolated --with "$wheel" ctrlagent agents list
```

This smoke installs the wheel artifact, not the editable checkout.

## Type Checking

Strict mypy covers the importable library under `libs/py_agent_ctrl` and the
thin runnable shells under `apps`. Tests are intentionally outside the strict
mypy target for now.

## Coverage

Coverage is measured for `libs/py_agent_ctrl` with a 90% regression floor. The
current baseline measured during QA hardening was 92% with live-agent integration
tests skipped by default. Manual live-agent tests are useful for behavior
confidence, but they are not required to satisfy the coverage floor.

## Live Integration Tests

Tests marked `live` invoke real external agent CLIs. They are excluded from the
normal local quality lane. They are manual-only: do not add scheduled live-agent
runs.

Run one configured provider when its CLI is installed and authenticated:

```bash
PY_AGENT_CTRL_RUN_LIVE_INTEGRATION=1 PY_AGENT_CTRL_LIVE_AGENTS=codex uv run python -m pytest -q tests/integration -m live
```

Run all configured providers:

```bash
PY_AGENT_CTRL_RUN_LIVE_INTEGRATION=1 uv run python -m pytest -q tests/integration -m live
```

Provider names and CLI binaries:

| Provider | `PY_AGENT_CTRL_LIVE_AGENTS` value | CLI binary |
|----------|-----------------------------------|------------|
| Claude Code | `claude-code` | `claude` |
| Codex | `codex` | `codex` |
| Gemini | `gemini` | `gemini` |
| OpenCode | `opencode` | `opencode` |
| Pi | `pi` | `pi` |

Before running live tests, check local CLI availability and versions:

```bash
for cli in claude codex gemini opencode pi; do
  command -v "$cli" >/dev/null && "$cli" --version || printf '%s not installed\n' "$cli"
done
```

The integration helper skips tests with explicit messages when
`PY_AGENT_CTRL_RUN_LIVE_INTEGRATION` is not set, a provider is not selected in
`PY_AGENT_CTRL_LIVE_AGENTS`, or a required CLI binary is missing from `PATH`.

## Ruff Scope

Ruff currently enforces formatting plus a conservative lint baseline:

- `E`, `F`, and `I` for pycodestyle, pyflakes, and import sorting.
- `B`, `UP`, `SIM`, and `RUF` for common bug risks, modernization, simple
  simplifications, and Ruff-specific checks.

`PTH` and `PL` rules are intentionally deferred because they can create broader
style churn. Add them later only when the resulting changes are clearly worth
the maintenance cost.
