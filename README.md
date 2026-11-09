# test-adapters

## 1. Purpose

`test-adapters` runs a project's tests with pytest and returns one normalised result. Callers read one result schema and one set of exit codes. They do not parse framework output.

The walking skeleton runs pytest only. jest is detected but cannot run yet (Phase 6).

## 2. Where to find the code

| Item | File | Line |
|------|------|------|
| CLI entry point (`main`) | `src/test_adapters/cli.py` | 70 |
| CLI run flags (list of valid names) | `src/test_adapters/cli.py` | 21 |
| `run` handler (flags, refusal of unimplemented flags) | `src/test_adapters/cli.py` | 114 |
| Refusal of unimplemented flags | `src/test_adapters/cli.py` | 134 |
| Python API: `detect` | `src/test_adapters/api.py` | 37 |
| Python API: `run` | `src/test_adapters/api.py` | 42 |
| Python API: `run_all` | `src/test_adapters/api.py` | 91 |
| Python API: `parse` | `src/test_adapters/api.py` | 108 |
| Python API: `parse_text` | `src/test_adapters/api.py` | 117 |
| Python API: `doctor` | `src/test_adapters/api.py` | 139 |
| Framework detection | `src/test_adapters/detection.py` | 11 |
| Process run and timeout | `src/test_adapters/execution.py` | 25 |
| POSIX kill of the process group | `src/test_adapters/execution.py` | 98 |
| Exit code map (ADR 0002) | `src/test_adapters/combine.py` | 15 |
| Overall status of several results | `src/test_adapters/model.py` | 45 |
| pytest adapter: detect, command, parse | `src/test_adapters/adapters/pytest_adapter.py` | 32 |
| JUnit parse and collection, no-test checks | `src/test_adapters/adapters/pytest_adapter.py` | 54 |
| Traceback `path:line` match | `src/test_adapters/adapters/pytest_adapter.py` | 28 |
| jest adapter (detect only) | `src/test_adapters/adapters/jest_adapter.py` | 19 |
| Adapter registry | `src/test_adapters/adapters/registry.py` | 17 |
| Text view | `src/test_adapters/render.py` | 20 |
| JSON view | `src/test_adapters/render.py` | 83 |
| Result types and rules | `src/test_adapters/model.py` | 185 |
| Skeleton test (real CLI on a fixture) | `tests/test_walking_skeleton.py` | 1 |
| Invariant tests | `tests/test_skeleton_invariants.py` | 1 |
| Fixture project (3 pass, 1 fail, 1 skip) | `tests/fixtures/pytest_mixed/` | — |
| One command for every check | `scripts/check` | 1 |
| CI matrix | `.github/workflows/ci.yml` | 1 |
| Import boundaries | `pyproject.toml` | 36 |

## 3. How it works

### 3.1 Run a pytest project

1. The CLI parses the flags. An unknown flag exits with code 2 and lists the valid run flags.
2. `api.run` checks the framework. With no `--framework`, it calls `detect`.
3. With one framework found, `run` checks that the adapter's requirements are installed. A missing requirement returns `tool_missing`.
4. The adapter builds the command. For pytest it runs `pytest -q --junitxml=<tmp>/junit.xml` with the interpreter that runs the CLI.
5. `run_process` starts the command in its own process group. It writes stdout to a file.
6. On timeout, it sends SIGTERM to the group, waits for the grace period, then sends SIGKILL.
7. The adapter parses the JUnit file. A failure's `file` and `line` come from the last `path:line: ErrorType` line in its traceback.
8. The CLI prints the view and exits with the code for the status.

### 3.2 Detect frameworks

`detect` asks each registered adapter whether its project files exist. It reads files only. It runs no test.

- pytest matches `pytest.ini`, `conftest.py`, a `[tool.pytest` section in `pyproject.toml`, or `tests/test_*.py`.
- jest matches `jest.config.*`, or a `package.json` with a `jest` key, a `jest` script, or `jest` in `devDependencies`.

With no arguments, the CLI runs `detect` and `doctor`. It lists each framework and stops.

### 3.3 Exit codes

| Status | Exit code |
|--------|-----------|
| passed | 0 |
| failed | 1 |
| usage error (not a status) | 2 |
| error | 3 |
| timeout | 4 |

`exit_code_for` in `src/test_adapters/combine.py` (line 23) is the only source for codes 0, 1, 3 and 4.

### 3.4 Status rules

- `error` ranks first, then `timeout`, `failed`, `passed` (`STATUS_RANK`, `src/test_adapters/model.py`, line 45).
- A `TestResult` with counts satisfies `total == passed + failed + skipped + errors`. The constructor rejects any other value (`src/test_adapters/model.py`, line 185).
- Counts are `null` only for `error` and `timeout` without a count source.

### 3.5 Errors the pytest adapter reports

| Condition | Result |
|-----------|--------|
| No report file, and the run timed out | `timeout` with counts `null` |
| No report file, run finished | `error`, `unparseable_report` |
| Report is not valid XML | `error`, `unparseable_report` |
| A suite fails to load (error without class name) | `error`, `collection` |
| Report has no test cases | `error`, `no_tests` |

## 4. Settings

| Setting | Value | Effect | Where |
|---------|-------|--------|-------|
| `--timeout` | 600 seconds | Stops the run and returns `timeout` | `cli.py` line 51 |
| `kill_grace_seconds` | 5 seconds | Time between SIGTERM and SIGKILL | `model.py` line 116 |
| `max_output_bytes` | 5 MiB | Tail of stdout kept on disk | `model.py` line 117 |
| `--framework` | none | Auto-detect; `all` runs each detected framework | `cli.py` line 116 |
| `--cwd` | `.` | Project directory | `cli.py` line 59 |
| `--json`, `--result-file` | off | Full JSON on stdout, or written to a file | `cli.py` lines 57-58 |
| `--full` | off | Lifts the 200-character message cut | `cli.py` line 55 |

`test-adapters.toml` is not read yet. `load_config` is a stub (`src/test_adapters/config.py`, line 36).

## 5. Install

Before you start, install these tools:

- `uv` (https://docs.astral.sh/uv/). `scripts/check` and CI call `uvx` for every tool.
- Python 3.11 or later.
- pytest, in the interpreter that runs the CLI. Run `uvx --with pytest` to get it.

Install methods:

- Run from a checkout with `PYTHONPATH=src python -m test_adapters.cli`.
- Build a wheel with `scripts/check`. The wheel is not published (PyPI upload needs owner approval).

Install check:

1. Run `PYTHONPATH=src python -m test_adapters.cli doctor`.
2. Confirm each framework line says `available` or `missing`.

Changing settings: flags only in this release. Config file support is not built.

## 6. Validate

### 6.1 One command

Run `scripts/check` from the repo root. It runs, in order: import boundaries, lint, strict type check, tests, and a wheel build.

### 6.2 Output

Import boundaries, lint and type check, from the last run:

```
Contracts: 4 kept, 0 broken.
All checks passed!
Success: no issues found in 15 source files
```

Tests, from the last run:

```
...............................                                          [100%]
31 passed in 1.11s
```

`31 passed` is 26 invariant tests and 5 skeleton tests.

### 6.3 Levels

| Level | Test | What it proves |
|-------|------|----------------|
| Invariants | `tests/test_skeleton_invariants.py` | Result rules, immutability, registry, names, coverage wire form |
| Skeleton | `tests/test_walking_skeleton.py` | The real CLI, in a subprocess, on the fixture |

Skeleton tests:

| Test | Proves |
|------|--------|
| `test_run_default_view_reports_the_counts_and_failure` | Counts 3 passed, 1 failed, 1 skipped of 5; file and line of the failure; exit 1 |
| `test_run_json_is_the_complete_result` | `--result-file` writes the full JSON with the same counts and line 17 |
| `test_detect_runs_nothing_and_finds_pytest` | No-argument mode lists pytest and runs no test |
| `test_parse_matches_run_on_the_same_project` | `parse` on the JUnit file gives the same counts and status as `run` |
| `test_unknown_flag_is_a_usage_error` | Unknown flag exits 2 and names the valid flags |

### 6.4 Problems and solutions

| Problem | Solution |
|---------|----------|
| `uvx: command not found` | Install uv: https://docs.astral.sh/uv/ |
| `tool_missing` for pytest | Run through `uvx --with pytest`, or install pytest in the interpreter |
| `no framework detected` | Pass `--cwd <dir>` or `--framework <name>` |
| `status: error`, `unparseable_report` | Run the test command by hand and read its output |

## 7. Known limits

- **Windows.** The Windows kill path is a stub (`src/test_adapters/execution.py`, line 93). Windows is not tested. Issue #11 tracks the test run on Windows.
- **jest.** Detection works. Running and parsing jest does not. A jest run returns `tool_missing` with a message, and `--framework all` reports jest as its own error.
- **Flags not built.** `--coverage`, `--retry-failed`, `--retry-mode` (non-default) and `--fields` exit with code 2 and say they are not implemented. They are not ignored.
- **Config file.** `test-adapters.toml` is not read.
- **Timeout timing.** A timed-out pytest run takes the timeout plus the grace period. A measured run with a 2-second timeout took 7.0 seconds.
- **Timeout detail.** The current test is not named on timeout. Stdout parsing is not built.
- **`doctor` checks presence only.** It checks that `pytest` is importable. It does not check the version.
- **`fields` is ignored by the view.** The text view accepts a `fields` argument but does not print extra fields yet.
- **Stdout parsing.** `parse_text` returns `unparseable_report` for pytest. It does not read counts from stdout.
- **Process kill.** The POSIX kill sends SIGTERM and SIGKILL to the process group only. Processes that leave the group are not killed.

## 8. Glossary

| Term | Meaning |
|------|---------|
| Adapter | A module that knows one framework: how to detect it, run it and parse its report. |
| Framework | A test tool that an adapter supports. Here, pytest or jest. |
| Status | The verdict of one result: `passed`, `failed`, `error` or `timeout`. |
| Error code | The reason for status `error`: for example `tool_missing` or `collection`. |
| Result | A `TestResult` for one framework. |
| Combined result | A `CombinedResult`: one result per detected framework, plus an overall status. |
| Degraded | A result whose counts come from stdout and are lower bounds. Not produced yet. |
| Flaky | A test that failed, then passed on retry. Not produced yet. |
| Selector | A file path or node ID that limits a run. |
| Report | The machine-readable output of a framework run, such as JUnit XML. |

## Status

Implemented, not tested on Windows. The code runs on macOS and Linux in CI.
