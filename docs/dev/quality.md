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
uv export --format requirements.txt --extra dev --no-hashes --no-emit-project --locked | uvx pip-audit --no-deps --disable-pip -r /dev/stdin
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

## Docs Examples

Safe local README and user-doc examples are covered by feature smoke tests:

```bash
uv run python -m pytest -q tests/feature/test_docs_examples.py tests/feature/test_ctrlagent_cli.py
```

The docs classify examples into two groups: safe local metadata and builder
checks, or live-agent examples that launch external CLIs. Live-agent examples
must remain labeled as requiring the selected provider CLI to be installed and
authenticated.

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

## Minimal Security Audit

Audit the locked runtime and dev dependency set from `uv.lock`:

```bash
uv export --format requirements.txt --extra dev --no-hashes --no-emit-project --locked | uvx pip-audit --no-deps --disable-pip -r /dev/stdin
```

The export is fully pinned, so `pip-audit` runs with `--no-deps` and
`--disable-pip` instead of creating its own resolver environment. This avoids
environment-specific `ensurepip` failures and keeps the audit tied to the
checked-in `uv.lock`.

The first hardening pass intentionally does not add Semgrep, Bandit, or
gitleaks. Subprocess execution is expected behavior in this library, so broad
static security scanners should be added only after a concrete finding or
policy need justifies the extra noise.

Dependency update automation is also not added in this pass because this is a
plain git repository without an active CI/CD pipeline. Revisit Dependabot or
Renovate when the repository has an active hosted workflow that will actually
run the hardened quality lane on proposed updates.

## Subprocess Boundary Review

The core process boundary currently has the expected first-pass safeguards:

- commands are built and executed as argv lists, with no shell invocation;
- `cwd` is checked before blocking subprocess execution;
- subprocess environments are copied per command and provider overrides are
  applied explicitly;
- Claude Code-specific inherited environment variables are removed before
  launch to avoid stale configuration bleed-through;
- blocking and streaming execution paths both have timeout behavior;
- failure reporting stores a bounded stderr tail instead of unbounded output.

Future reviews should keep focusing on argv construction, provider-specific
environment sanitization, working-directory handling, timeout consistency, and
whether any diagnostic output could expose secrets.
