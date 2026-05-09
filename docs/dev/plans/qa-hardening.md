# QA Hardening Plan

bd epic: `bd-4g1` (`Harden py-agent-ctrl QA and release checks`)

## Goal

Harden `py-agent-ctrl` as both a Python library and the `ctrlagent` CLI by turning the current ad hoc quality checks into a layered, repeatable QA system.

The target state is:

- fast pull-request checks catch formatting, lint, typing, unit, feature, regression, packaging, and docs/example failures;
- slower or credentialed real-agent checks are available on demand and on a schedule;
- release confidence includes wheel installability, CLI entrypoint sanity, dependency/security checks, and public API compatibility smoke tests;
- local developer commands match CI, avoid stale virtualenv script problems, and are documented in one place.

## Current Baseline

The repository already has a useful baseline:

- `pyproject.toml` declares dev dependencies for `pytest`, `ruff`, and `mypy`, plus strict mypy over `libs/py_agent_ctrl`.
- `.github/workflows/ci.yml` runs `uv sync --extra dev`, `ruff check`, `mypy libs/py_agent_ctrl`, and `pytest -q`.
- Tests are split across `tests/unit`, `tests/feature`, `tests/integration`, and `tests/regression`.
- Real-agent integration tests exist for Claude Code, Codex, Gemini, OpenCode, and Pi, but they skip unless `PY_AGENT_CTRL_RUN_LIVE_INTEGRATION=1` is set and the relevant CLI is installed.
- Local verification via module invocation passed:
  - `uv run python -m ruff check .`
  - `uv run python -m mypy libs/py_agent_ctrl`
  - `uv run python -m pytest -q` (`129 passed`, `10 skipped`)
  - `uv build --wheel`
  - `uv run python -m compileall -q apps libs tests`

Important local finding: direct console-script invocation currently fails for `uv run pytest` and `uv run mypy` because the scripts in `.venv/bin` have stale shebangs pointing at `/Users/ddebowczyk/projects/py-agent-ctrl/.venv/...`. Module invocation works and should be used in local docs/CI until the environment issue is fixed or guarded.

## External Guidance Used

- Ruff official configuration and formatter docs support using Ruff for both lint and `ruff format --check`.
- Ruff rules docs show the current `E`, `F`, `I` set is only a narrow subset of available checks.
- Mypy docs confirm strict mode is a bundle of additional checks and can be configured through `[tool.mypy]` in `pyproject.toml`.
- Pytest docs support centralizing pytest options in project configuration.
- pytest-cov docs support coverage configuration through pytest and coverage config.
- pip-audit documentation supports adding dependency vulnerability scanning to Python CI.

References:

- https://docs.astral.sh/ruff/configuration/
- https://docs.astral.sh/ruff/formatter/
- https://docs.astral.sh/ruff/rules/
- https://mypy.readthedocs.io/en/stable/getting_started.html
- https://mypy.readthedocs.io/en/stable/config_file.html
- https://docs.pytest.org/en/latest/customize.html
- https://pytest-cov.readthedocs.io/
- https://github.com/pypa/pip-audit

## Constraints

- Preserve the existing architecture: `apps/` for thin runnable shells, `libs/` for importable code, `resources/` for passive assets, `docs/`, and layered `command -> actions -> services`.
- Use `uv` for dependency management, execution, linting, and tests.
- Keep normal PR CI fast and deterministic. Do not require authenticated third-party agent CLIs on every pull request.
- Keep real-agent e2e tests opt-in, scheduled, or manually dispatched because they can consume tokens, require credentials, depend on external CLIs, and take longer.
- Avoid broad rewrites. The hardening should be incremental and independently mergeable.
- Use `bd` for task tracking; do not duplicate execution tracking with markdown task checkboxes.

## Proposed Quality Model

### Lane 1: Fast PR Gate

Runs on every push and pull request.

Recommended checks:

- `uv sync --extra dev`
- `uv run python -m ruff format --check .`
- `uv run python -m ruff check .`
- `uv run python -m mypy libs/py_agent_ctrl apps`
- `uv run python -m pytest -q tests/unit tests/feature tests/regression`
- `uv run python -m compileall -q apps libs tests`
- `uv build --wheel`
- install the built wheel into a clean temporary environment and run `ctrlagent agents list`

This lane should not run live-agent tests by default.

### Lane 2: Coverage Gate

Runs on pull requests after the first hardening pass and can be part of the fast gate once stable.

Recommended checks:

- add `pytest-cov`;
- measure coverage for `libs/py_agent_ctrl`;
- start with a realistic threshold based on the current measured value;
- raise thresholds gradually for parser, command-builder, subprocess, facade, and CLI code.

The first implementation should avoid an arbitrary threshold. It should measure the baseline, choose a floor that prevents regression, and document uncovered high-risk areas.

### Lane 3: Static Analysis Expansion

Expand lint/type checks beyond the current baseline.

Recommended checks:

- add `ruff format --check`;
- expand `ruff.lint.select` beyond `E`, `F`, and `I` with conservative rules such as `B`, `UP`, `SIM`, `RUF`, and selected `PTH`/`PL` rules where they fit the codebase;
- include `apps` in mypy;
- add type-focused public API smoke tests or pyright/basedpyright only if it catches issues mypy misses without adding too much maintenance load;
- keep tests out of strict mypy initially unless a targeted test-typing task proves the cost is low.

### Lane 4: Live-Agent E2E

Runs via `workflow_dispatch`, schedule, or a protected/manual label.

Recommended checks:

- matrix by provider: `claude-code`, `codex`, `gemini`, `opencode`, `pi`;
- set `PY_AGENT_CTRL_RUN_LIVE_INTEGRATION=1`;
- use `PY_AGENT_CTRL_LIVE_AGENTS` to select providers;
- run tests under `tests/integration`;
- produce explicit skipped/not-configured summaries when a provider binary or credential is missing;
- time-box individual agent calls and collect CLI version diagnostics.

This lane should distinguish unavailable infrastructure from library regressions.

### Lane 5: Security and Dependency Hygiene

Runs on PR and/or schedule.

Recommended checks:

- dependency vulnerability scan with `pip-audit` or equivalent;
- GitHub Dependabot or Renovate for Python/Actions updates;
- secret scanning with a local-friendly tool such as `gitleaks` if acceptable for the repo;
- optional Semgrep/Bandit pass focused on subprocess, shell, path, and environment handling.

The subprocess boundary is core to this library, so security checks should focus on argv construction, environment sanitization, working-directory handling, stderr/secret leakage, and timeout behavior.

### Lane 6: Docs and Example Drift

Runs on PR or as a docs-specific check.

Recommended checks:

- validate README and `docs/user/*.md` command snippets where possible;
- test Python snippets that do not require live agents;
- verify docs mention the correct local commands, especially module invocation if console scripts are stale;
- keep a single `make`/`just`/script-free command reference if the project prefers pure `uv` commands.

### Lane 7: Release Readiness

Runs before publishing.

Recommended checks:

- build wheel and sdist;
- install artifacts in a clean environment;
- import `py_agent_ctrl`;
- run `ctrlagent agents list`;
- check `py.typed` is included;
- verify README renders enough for package metadata;
- optionally run `twine check` or equivalent metadata validation.

## Task Breakdown

The following tasks should be created under epic `bd-4g1` after this plan is reviewed.

### 1. Normalize Local and CI Quality Commands

Purpose: make local verification and CI invocation reliable and identical.

Scope:

- update README and/or docs with canonical commands using `uv run python -m ...`;
- update `.github/workflows/ci.yml` to use module invocation for `ruff`, `mypy`, and `pytest`;
- add a concise quality command section to development docs;
- investigate whether stale `.venv/bin` shebangs can be repaired by recreating `.venv`, but do not rely on that as the only fix.

Verification:

- `uv run python -m ruff check .`
- `uv run python -m mypy libs/py_agent_ctrl`
- `uv run python -m pytest -q`

### 2. Add Formatting and Broaden Ruff Linting

Purpose: move from minimal linting to a stronger static lint baseline without creating noisy churn.

Scope:

- add `uv run python -m ruff format --check .` to CI;
- run `ruff format` only if needed and keep formatting changes isolated;
- expand lint rules conservatively;
- add per-file ignores only with narrow justification;
- document the chosen rule families.

Verification:

- `uv run python -m ruff format --check .`
- `uv run python -m ruff check .`

### 3. Expand Mypy Coverage to CLI Entrypoints

Purpose: ensure the shipped CLI layer is covered by static typing, not only `libs`.

Scope:

- include `apps` and `libs` in mypy configuration or CI command;
- decide whether `py_agent_ctrl.cli` and `apps/cli/main.py` need annotations or small refactors;
- keep strict mode unless a specific override is justified;
- avoid broad typing of tests in this task.

Verification:

- `uv run python -m mypy libs/py_agent_ctrl apps`
- `uv run python -m pytest -q tests/feature/test_ctrlagent_cli.py`

### 4. Add Coverage Measurement and Regression Threshold

Purpose: make test coverage visible and prevent silent erosion.

Scope:

- add `pytest-cov` to dev dependencies;
- configure coverage for `libs/py_agent_ctrl`;
- measure current baseline;
- choose an initial threshold that current tests pass without gaming the number;
- produce terminal and XML reports for CI;
- document intentionally uncovered live-agent paths.

Verification:

- `uv run python -m pytest --cov=py_agent_ctrl --cov-report=term-missing --cov-report=xml`

### 5. Build Clean Wheel Install Smoke Tests

Purpose: catch packaging and console-entrypoint regressions before release.

Scope:

- add CI step to run `uv build --wheel`;
- install the built wheel into a clean temp environment;
- verify `import py_agent_ctrl`;
- verify `ctrlagent agents list`;
- verify `py_agent_ctrl/py.typed` is present in the installed package.

Verification:

- `uv build --wheel`
- clean-environment install and smoke command execution.

### 6. Separate Fast Tests from Live-Agent E2E Tests

Purpose: make test layers explicit and avoid accidental slow/credentialed runs.

Scope:

- add pytest markers such as `unit`, `feature`, `regression`, `live`;
- mark real-agent tests under `tests/integration` as live;
- configure pytest marker registration;
- update CI fast lane to run non-live tests;
- preserve local command for running all non-live tests.

Verification:

- `uv run python -m pytest -q -m "not live"`
- `uv run python -m pytest -q tests/integration` should skip live tests unless enabled.

### 7. Add Manual/Scheduled Live-Agent E2E Workflow

Purpose: verify actual external CLIs without blocking every PR.

Scope:

- add GitHub Actions workflow or job with `workflow_dispatch`;
- allow selecting providers via input mapped to `PY_AGENT_CTRL_LIVE_AGENTS`;
- set `PY_AGENT_CTRL_RUN_LIVE_INTEGRATION=1`;
- collect provider CLI version diagnostics;
- make missing credentials/binaries visible as infrastructure skip, not silent success;
- keep timeouts bounded.

Verification:

- manually dispatch workflow for one configured provider;
- inspect logs for explicit provider status and test result.

### 8. Add Security and Dependency Scanning

Purpose: catch dependency vulnerabilities and obvious subprocess/env mistakes.

Scope:

- add `pip-audit` or equivalent dependency vulnerability scan;
- add Dependabot or Renovate config for GitHub Actions and Python dependencies;
- evaluate lightweight secret scanning with `gitleaks`;
- evaluate Bandit/Semgrep rules focused on subprocess, path, env, shell, and secret leakage;
- document any ignored findings with rationale.

Verification:

- dependency audit command passes or reports documented accepted risk;
- scanner configs exist and run in CI or scheduled workflow.

### 9. Add Docs and Example Validation

Purpose: prevent public README/docs snippets from drifting away from the actual API and CLI.

Scope:

- identify snippets in README and `docs/user/*.md`;
- convert safe Python examples into tests or doctest-style checks;
- add smoke tests for CLI examples that do not invoke live agents;
- update docs to reflect test layer commands and live-agent requirements.

Verification:

- docs/example verification command passes;
- README quickstart snippets match public API.

### 10. Add Release Readiness Checklist and Workflow

Purpose: define the final gate before publishing or tagging.

Scope:

- document release QA in `docs/dev`;
- include lint, type, non-live tests, coverage, wheel/sdist build, install smoke, docs check, and security scan;
- optionally add a manual release-check workflow;
- verify package metadata and README rendering if a suitable tool is added.

Verification:

- one documented command sequence or manual workflow completes end to end.

## Proposed Dependency Graph

Suggested execution order:

1. Normalize commands.
2. Add format and broaden Ruff.
3. Expand mypy to CLI entrypoints.
4. Add coverage.
5. Add wheel install smoke tests.
6. Separate fast tests from live-agent e2e tests.
7. Add manual/scheduled live-agent e2e workflow.
8. Add security and dependency scanning.
9. Add docs/example validation.
10. Add release readiness checklist/workflow.

Hard dependencies:

- task 2 depends on task 1;
- task 3 depends on task 1;
- task 4 depends on task 1;
- task 5 depends on task 1;
- task 7 depends on task 6;
- task 10 depends on tasks 2 through 9.

Tasks 6, 8, and 9 can proceed independently after task 1 if needed.

## Risks and Tradeoffs

- Expanded Ruff rules can create churn. Mitigation: add rule families incrementally and keep per-file ignores narrow.
- Coverage thresholds can incentivize low-value tests. Mitigation: set a baseline threshold first, then raise only around high-risk modules.
- Live-agent tests can be flaky, expensive, or blocked by credentials. Mitigation: keep them manual/scheduled, provider-scoped, and diagnostic-rich.
- Security scanners can produce noisy findings around intentional subprocess use. Mitigation: tune rules around actual risk areas instead of accepting broad ignore lists.
- Docs example testing can become brittle if examples are too high-level. Mitigation: only test snippets that can run without external agents, and smoke CLI commands that do not execute live providers.

## Open Questions for Review

- Should the project prefer pure `uv` commands only, or is adding a `justfile`/`Makefile` acceptable for discoverability?
- Should live-agent e2e run on a schedule, only manual dispatch, or both?
- Which providers have reliable credentials available in CI today?
- Is a second type checker such as pyright/basedpyright worth the maintenance cost, or should strict mypy remain the only type gate for now?
- Should security scanning be minimal (`pip-audit` plus Dependabot) or include Semgrep/Bandit/gitleaks from the first hardening pass?

## Review Decision Needed

This plan is ready for human review. After approval, create the child bd tasks under epic `bd-4g1` with full execution context and dependency links matching the proposed graph above.
