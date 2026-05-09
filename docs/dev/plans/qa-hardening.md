# QA Hardening Plan

bd epic: `bd-4g1` (`Harden py-agent-ctrl QA and release checks`)

## Goal

Harden `py-agent-ctrl` as both a Python library and the `ctrlagent` CLI by turning the current ad hoc quality checks into a layered, repeatable QA system.

The target state is:

- fast local/repo checks catch formatting, lint, typing, unit, feature, regression, packaging, and docs/example failures;
- slower or credentialed real-agent checks are available only on manual demand;
- release confidence includes wheel installability, CLI entrypoint sanity, dependency/security checks, and public API compatibility smoke tests;
- local developer commands are `uv`-only, avoid stale virtualenv script problems, and are documented in one place.

## Current Baseline

The repository already has a useful baseline:

- `pyproject.toml` declares dev dependencies for `pytest`, `ruff`, and `mypy`, plus strict mypy over `libs/py_agent_ctrl`.
- `.github/workflows/ci.yml` exists and documents a basic quality lane, but this repository should not assume an active CI/CD pipeline.
- Tests are split across `tests/unit`, `tests/feature`, `tests/integration`, and `tests/regression`.
- Real-agent integration tests exist for Claude Code, Codex, Gemini, OpenCode, and Pi, but they skip unless `PY_AGENT_CTRL_RUN_LIVE_INTEGRATION=1` is set and the relevant CLI is installed.
- Local verification via module invocation passed:
  - `uv run python -m ruff check .`
  - `uv run python -m mypy libs/py_agent_ctrl`
  - `uv run python -m pytest -q` (`129 passed`, `10 skipped`)
  - `uv build --wheel`
  - `uv run python -m compileall -q apps libs tests`

Important local finding: direct console-script invocation currently fails for `uv run pytest` and `uv run mypy` because the scripts in `.venv/bin` have stale shebangs pointing at `/Users/ddebowczyk/projects/py-agent-ctrl/.venv/...`. Module invocation works and should be used in local docs and optional workflows until the environment issue is fixed or guarded.

## External Guidance Used

- Ruff official configuration and formatter docs support using Ruff for both lint and `ruff format --check`.
- Ruff rules docs show the current `E`, `F`, `I` set is only a narrow subset of available checks.
- Mypy docs confirm strict mode is a bundle of additional checks and can be configured through `[tool.mypy]` in `pyproject.toml`.
- Pytest docs support centralizing pytest options in project configuration.
- pytest-cov docs support coverage configuration through pytest and coverage config.
- pip-audit documentation supports adding dependency vulnerability scanning to Python projects.

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
- Use `uv` for dependency management, execution, linting, tests, and documented command entrypoints. Do not add `Makefile`, `justfile`, or wrapper scripts in the first hardening pass.
- Treat this as a git repository, not an active CI/CD deployment system. Workflow files may be kept as optional automation/documentation, but the primary contract is reproducible local `uv` commands.
- Keep real-agent e2e tests manually dispatched only because they can consume tokens, require credentials, depend on external CLIs, and take longer.
- Avoid broad rewrites. The hardening should be incremental and independently mergeable.
- Use `bd` for task tracking; do not duplicate execution tracking with markdown task checkboxes.

## Proposed Quality Model

### Lane 1: Fast Local Quality Gate

Runs locally before commit/push and may also be mirrored by optional GitHub workflow files.

Recommended checks:

- `uv sync --extra dev`
- `uv run python -m ruff format --check .`
- `uv run python -m ruff check .`
- `uv run python -m mypy libs/py_agent_ctrl apps`
- `uv run python -m pytest -q tests/unit tests/feature tests/regression`
- `uv run python -m compileall -q apps libs tests`
- `uv build --wheel`
- install the built wheel into a clean temporary environment and run `ctrlagent agents list`

This lane should not run live-agent tests by default and should remain expressible as plain `uv` commands.

### Lane 2: Coverage Gate

Runs locally after the first hardening pass and can be part of the fast local gate once stable.

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
- evaluate pyright/basedpyright only if a documented spike shows it catches meaningful issues mypy misses, such as stricter public API use, enum narrowing, Pydantic model access, or call-site compatibility. Strict mypy remains the default type gate unless the second checker proves its value;
- keep tests out of strict mypy initially unless a targeted test-typing task proves the cost is low.

### Lane 4: Live-Agent E2E

Runs only by manual invocation. If a GitHub workflow is kept, it should use `workflow_dispatch` only; no schedule.

Recommended checks:

- matrix by provider: `claude-code`, `codex`, `gemini`, `opencode`, `pi`;
- set `PY_AGENT_CTRL_RUN_LIVE_INTEGRATION=1`;
- use `PY_AGENT_CTRL_LIVE_AGENTS` to select providers;
- run tests under `tests/integration`;
- produce explicit skipped/not-configured summaries when a provider binary or credential is missing;
- time-box individual agent calls and collect CLI version diagnostics.

This lane should distinguish unavailable infrastructure from library regressions.

### Lane 5: Minimal Security and Dependency Hygiene

Runs locally and can be mirrored by optional workflow files. Keep the first pass minimal.

Recommended checks:

- dependency vulnerability scan with `pip-audit` or equivalent;
- optionally add Dependabot or Renovate for Python/GitHub Actions updates if the repo will use GitHub-native automation;
- defer Semgrep, Bandit, and gitleaks unless a later review shows a concrete need.

The subprocess boundary is core to this library, but the first hardening pass should start with dependency audit and documented subprocess review notes rather than a broad scanner rollout.

### Lane 6: Docs and Example Drift

Runs locally or as an optional docs-specific workflow check.

Recommended checks:

- validate README and `docs/user/*.md` command snippets where possible;
- test Python snippets that do not require live agents;
- verify docs mention the correct local commands, especially module invocation if console scripts are stale;
- keep a single command reference using pure `uv` commands.

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

### 1. Normalize Local and Optional Workflow Quality Commands

Purpose: make local verification reliable and keep optional workflow files aligned with the same commands.

Scope:

- update README and/or docs with canonical `uv` commands using `uv run python -m ...`;
- update `.github/workflows/ci.yml`, if retained, to use module invocation for `ruff`, `mypy`, and `pytest`;
- add a concise quality command section to development docs;
- investigate whether stale `.venv/bin` shebangs can be repaired by recreating `.venv`, but do not rely on that as the only fix.

Verification:

- `uv run python -m ruff check .`
- `uv run python -m mypy libs/py_agent_ctrl`
- `uv run python -m pytest -q`

### 2. Add Formatting and Broaden Ruff Linting

Purpose: move from minimal linting to a stronger static lint baseline without creating noisy churn.

Scope:

- add `uv run python -m ruff format --check .` to the documented quality lane and optional workflow;
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

- include `apps` and `libs` in mypy configuration and documented quality commands;
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
- produce terminal reports by default and XML reports only if useful for optional workflow artifacts or future tooling;
- document intentionally uncovered live-agent paths.

Verification:

- `uv run python -m pytest --cov=py_agent_ctrl --cov-report=term-missing --cov-report=xml`

### 5. Build Clean Wheel Install Smoke Tests

Purpose: catch packaging and console-entrypoint regressions before release.

Scope:

- add documented quality step, and optional workflow step if retained, to run `uv build --wheel`;
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
- update the fast local lane and optional workflow to run non-live tests;
- preserve local command for running all non-live tests.

Verification:

- `uv run python -m pytest -q -m "not live"`
- `uv run python -m pytest -q tests/integration` should skip live tests unless enabled.

### 7. Add Manual Live-Agent E2E Command/Workflow

Purpose: verify actual external CLIs without blocking the normal local quality workflow.

Scope:

- add a documented manual command and, if useful, a GitHub Actions workflow with `workflow_dispatch` only;
- allow selecting providers via input mapped to `PY_AGENT_CTRL_LIVE_AGENTS`;
- set `PY_AGENT_CTRL_RUN_LIVE_INTEGRATION=1`;
- collect provider CLI version diagnostics;
- make missing credentials/binaries visible as infrastructure skip, not silent success;
- keep timeouts bounded.

Verification:

- manually run the command or dispatch the workflow for one configured provider;
- inspect logs for explicit provider status and test result.

### 8. Add Security and Dependency Scanning

Purpose: catch dependency vulnerabilities and obvious subprocess/env mistakes.

Scope:

- add `pip-audit` or equivalent dependency vulnerability scan;
- document how to run the audit locally with `uv`;
- optionally add Dependabot or Renovate only if GitHub-native automation is desired for this git repo;
- defer gitleaks, Bandit, and Semgrep to later tasks unless a concrete finding justifies them;
- document any ignored findings with rationale.

Verification:

- dependency audit command passes or reports documented accepted risk;
- minimal scanner command is documented and passes or reports documented accepted risk.

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
- optionally add a manual release-check workflow only if useful as a repo-local automation aid;
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
7. Add manual live-agent e2e command/workflow.
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
- Live-agent tests can be flaky, expensive, or blocked by credentials. Mitigation: keep them manual-only, provider-scoped, and diagnostic-rich.
- Security scanners can produce noisy findings around intentional subprocess use. Mitigation: start minimal with dependency audit and add broader scanners only when justified by concrete risk.
- Docs example testing can become brittle if examples are too high-level. Mitigation: only test snippets that can run without external agents, and smoke CLI commands that do not execute live providers.

## Review Decisions

- Use pure `uv` commands for now. Do not add a `Makefile` or `justfile`.
- Live-agent e2e should be manual only. Do not add scheduled live-agent runs.
- There is no active CI/CD pipeline and no reliable provider credentials available in CI today. Treat this as a git repo with reproducible local commands and optional workflow files.
- Strict mypy remains the default type gate. A second checker such as pyright/basedpyright is acceptable only after a bounded spike justifies the added value.
- Keep security scanning minimal in the first pass: dependency audit plus optional dependency-update automation. Defer Semgrep, Bandit, and gitleaks.

## Review Decision Needed

This plan has incorporated the first review decisions. After explicit approval to proceed, create the child bd tasks under epic `bd-4g1` with full execution context and dependency links matching the proposed graph above.
