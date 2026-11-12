# test-adapters: Requirements

> Status: Draft v0.5 · Self-contained. This document does not depend on any other project. Phasing is in [roadmap.md](./roadmap.md).

---

## 1. Purpose

`test-adapters` runs a project's tests with pytest or jest and returns one normalised result, whichever framework produced it. Callers deal with one result schema and one set of exit codes. They never parse framework output.

Typical callers:

- A coding agent that runs tests after every change and must read the outcome cheaply.
- A CI wrapper or merge queue that decides "green or not" from an exit code.
- A metrics or reporting tool that ingests the result as JSON.

## 2. Scope and Non-Goals

**In scope**

- Framework detection, command construction, execution with timeout, report parsing.
- A single `TestResult` schema, including failures, flaky tests and optional coverage.
- Running a subset of tests, and re-running failures.
- A short, token-efficient text view for agents, and a complete JSON view for programs.
- A small adapter interface for adding frameworks.

**Non-goals**

- Deciding which tests must exist, enforcing TDD, or setting coverage policy. The library returns numbers; callers apply thresholds.
- Checking out branches or otherwise modifying the repository. The caller sets the working directory.
- Test generation.
- Test selection by changed files (impact analysis). Not in the first release; planned for a later phase (see [roadmap.md](./roadmap.md)).

## 3. Users and Usage

| Caller | How it calls | What it reads |
|--------|--------------|---------------|
| CI wrapper / merge queue | `test-adapters run --json --result-file <path>` | The exit code first; the result file only if it wants detail |
| Coding agent in a fix loop | `test-adapters run --select <files>` | The default text view |
| Agent at session start | `test-adapters` with no arguments | Detected framework and `doctor` status |
| Metrics / reporting tool | Python API `run()` or `parse()` | `TestResult` object or JSON |

## 4. Data Model

### 4.1 TestRequest

```
{ cwd, framework?, command_override?, select[]?, timeout_seconds,
  parallelism?, coverage: bool, env{}, retry_failed: int, retry_mode,
  require_tests: bool, kill_grace_seconds: int, max_output_bytes: int }
```

- `select` is a list of test file paths or node IDs.
- `framework` omitted means auto-detect. If more than one framework is detected, the run fails with `ambiguous` (4.3). `framework: "all"` runs every detected framework and returns a combined result (4.4).
- `retry_mode` is `file` (default) or `isolated`. It has no effect when `retry_failed` is 0. See 6.4.
- `kill_grace_seconds` (default 5) and `max_output_bytes` (default 5 MiB) are the execution settings in 6.3 and section 7. They are request fields so a value in `test-adapters.toml` reaches `run()`.
- `parallelism` is an integer or `"auto"` (default). `"auto"` is a request value, not a missing one; omitting `framework` is what means auto-detect.
- `framework` is a registered adapter name, or `"all"`. The set of names is open (5.2), so an unknown name is a usage error raised by the registry, not a type error.
- A request is immutable. `env` is a read-only mapping.

### 4.2 TestResult

```json
{
  "schema_version": 1,
  "framework": "pytest",
  "status": "passed",
  "error": null,
  "total": 120, "passed": 118, "failed": 1, "skipped": 1, "errors": 0,
  "duration_ms": 8421,
  "failures": [
    { "name": "tests/test_x.py::test_y", "message": "assert 1 == 2",
      "file": "tests/test_x.py", "line": 42 }
  ],
  "flaky": [
    { "name": "tests/test_z.py::test_w", "attempts": 2, "retry_mode": "file" }
  ],
  "coverage": { "line_percent": 83.1,
                "files": [ { "path": "...", "line_percent": 70.0 } ] },
  "warnings": [],
  "degraded": false,
  "raw": { "exit_code": 1, "stdout_path": "...", "report_path": "..." },
  "command": "pytest ..."
}
```

`status` is one of:

| Status | Meaning |
|--------|---------|
| `passed` | Ran. No failures or errors. A test that failed and then passed on retry is still `passed` and appears in `flaky`. |
| `failed` | Ran. At least one test still fails after retries. |
| `error` | Could not run to a trustworthy result. See the error codes in 4.3. |
| `timeout` | Killed at the time limit. Both frameworks write their report only at the end of a run, so a killed run usually has none. Counts then come from stdout progress if parseable (`degraded = true`), otherwise they are `null` (see 6.3). |

Rules:

- `error` is `null` unless `status == error`. Otherwise it is `{ "code": "<code>", "message": "...", "hint": "..." }`.
- `framework` is `null` only for an `ambiguous` error, because no single framework was chosen (4.3).
- A `TestResult` that breaks these rules cannot be built. The constructor rejects it, so an adapter cannot return `passed` with failures, `failed` with `null` counts, or counts that do not add up.
- `failures[].line` is `null` when no line can be determined. `file` is `null` when no file can be determined.
- `flaky` lists tests that failed at least once and passed on a later attempt. It is `[]` when there are none. Each entry records the `retry_mode` that produced the pass, so a caller can discount `isolated` passes (see 6.4).
- `warnings` is a list of strings: requests that could not be honoured (for example, parallelism requested but the plugin is missing), or missing coverage tooling.
- `degraded` is `true` when no machine-readable report was available and counts came from parsing stdout. Counts are then best-effort.
- `--json` always carries complete messages. Truncation applies only to the default text view.
- Counts are `null` (not `0`) when no count source exists, which can happen only for `timeout` and `error`. Otherwise the invariant `total = passed + failed + skipped + errors` holds, and each test is counted once, by its final outcome.

**Outcome mapping.** Every framework-specific outcome maps to exactly one counted outcome:

| Counted as | pytest | jest |
|------------|--------|------|
| `passed` | passed; xpass (non-strict); a test that failed then passed on retry | passed |
| `failed` | failed; xpass under `xfail_strict` (pytest already reports it as a failure) | failed |
| `skipped` | skipped; xfail (expected failure occurred) | pending, skipped, todo, disabled |
| `errors` | error in fixture setup or teardown, outside the test body | not used |

- `errors > 0` makes `status` `failed`, because the run completed and tests did not pass.
- A suite that cannot load (pytest collection error; jest "Test suite failed to run") is never counted. It is `status = error`, `error.code = collection`.
- xfail and todo are folded into `skipped` deliberately. The schema stays small, and neither affects the verdict.
- The pytest rows are expected to match the JUnit representation, and the jest rows are unconfirmed. Both are in the verification list in 6.2.

### 4.3 Error codes

| Code | Cause | Notes |
|------|-------|-------|
| `tool_missing` | Framework binary absent | Include an install hint |
| `collection` | Import or syntax error prevents tests from loading | Include the first error message |
| `no_tests` | Zero tests collected and `require_tests` is true | |
| `unparseable_report` | Report missing or malformed | Include the stdout path. A stdout fallback is attempted first |
| `ambiguous` | Several frameworks detected and none chosen | Fails before running anything. The message lists the detected frameworks and suggests `--framework <name>`, `--framework all`, or pinning `framework` in config |
| `unsupported_selector` | `select` cannot be expressed for the framework | Include the reason. Also returned when `select` is combined with `framework: all`, because a path cannot be routed to a framework unambiguously |

Failing tests are results, not errors.

An `ambiguous` result has `framework: null` and `null` counts, and its message lists the detected frameworks.

### 4.4 CombinedResult

Returned by `run_all` and by `run --framework all`.

```json
{ "schema_version": 1, "status": "failed",
  "results": [ { "...": "TestResult for pytest" },
               { "...": "TestResult for jest" } ] }
```

- `results` has one `TestResult` per detected framework, in detection order. With one detected framework it still has one entry, so the shape never changes under the caller.
- Frameworks run one after another, not concurrently, so they do not contend for ports, CPU or the working tree. Each run has its own `timeout_seconds`.
- A framework that cannot run (for example `tool_missing`) appears with its own `status: error`. It does not stop the others.
- The overall `status` is derived from `results` and is never stored, so it cannot disagree with them. It is the worst entry, in this order: `error`, `timeout`, `failed`, `passed`. `error` ranks first because a framework with no trustworthy result means the repo is not known to be green.
- Counts are not summed. Each `TestResult` keeps its own.
- The exit code follows the overall `status` (5.4). `--result-file` writes the `CombinedResult`.

## 5. Interface

### 5.1 Python API

| Operation | Description |
|-----------|-------------|
| `detect(cwd) -> [Framework]` | Ordered candidates from project files (section 6.1) |
| `run(request) -> TestResult` | Build the command, execute, parse. `framework: "all"` is a usage error here; use `run_all` |
| `run_all(request) -> CombinedResult` | Run every detected framework in turn (4.4) |
| `parse(framework, report_path) -> TestResult` | Parse an existing report file without running anything |
| `parse_text(framework, stdout) -> TestResult` | Parse captured stdout when no report exists. Counts are degraded (6.3). Split from `parse` in v0.5 |
| `adapter_info(framework) -> { command_template, report_format, requires[] }` | Introspection |
| `doctor(cwd) -> Report` | Verify the framework and its reporter are installed |

### 5.2 Adapter interface (for adding frameworks)

```
name, command_template, report_format          (strings; used by adapter_info)
detect(cwd) -> bool
build_command(request, workdir) -> argv[] + env + report_paths
parse(report_files, exit_code, stdout, timed_out) -> TestResult
requires() -> [binary or plugin]
```

- `report_files` are the report paths that exist after the run. An empty list means no report: the adapter reads `stdout` and sets `degraded`. `exit_code` is `null` for a killed run.
- `parse(framework, report_path)` in 5.1 calls the adapter with one report file and no stdout. `parse_text(framework, stdout)` calls it with no report file.
- Adding a framework must not require changing existing code. Adapters register through a registry, in a fixed detection order. The built-in pytest and jest adapters register when the package is imported. A second registration of one name is a usage error.

### 5.3 CLI

| Command | Behaviour |
|---------|-----------|
| `test-adapters` (no arguments) | Runs `detect` and `doctor` for the current directory and lists every detected framework. If several are detected, it says so and prints the `--framework` options. **Does not run any test.** |
| `test-adapters run [flags]` | Runs the tests and prints the default view |
| `test-adapters run --json` | Prints the full `TestResult` as JSON to stdout |
| `test-adapters doctor` | Reports framework and reporter availability |
| `test-adapters parse <framework> <file>` | Parses an existing report |

Flags for `run`: `--select <path|nodeid>` (repeatable), `--framework <name|all>`, `--timeout <s>`, `--retry-failed <n>`, `--retry-mode <file|isolated>`, `--coverage`, `--full`, `--fields <list>`, `--json`, `--result-file <path>`, `--cwd <dir>`.

`--result-file <path>` writes the complete JSON result to that path in addition to the chosen stdout view. It exists so a caller that sees only the exit code can still fetch the detail.

### 5.4 Exit codes

Exit codes distinguish what a caller needs to branch on. They are part of the contract.

| Code | Meaning |
|------|---------|
| `0` | `status == passed` (includes a flaky pass) |
| `1` | `status == failed` |
| `2` | Usage error, such as an unknown flag |
| `3` | `status == error` (could not run to a trustworthy result) |
| `4` | `status == timeout` |

For `--framework all`, the code is derived from the overall status of the `CombinedResult` (4.4).

No other codes. A test failure is a real regression signal (1); codes 3 and 4 are environment or tooling faults that a caller may treat differently (for example, retry or halt rather than blame the change).

### 5.5 Default text view for `run`

The default view is for agents. Layout is illustrative, not a contract; the fields and rules below are.

```
status: failed
summary: 118 passed, 1 failed, 1 skipped of 120 (8.4s)
failures[1 of 1]{name,file,line,message}:
  tests/test_x.py::test_y,tests/test_x.py,42,"assert 1 == 2"
flaky: none
help[2]:
  test-adapters run --select tests/test_x.py::test_y   # rerun only this
  test-adapters run --full                              # untruncated messages
```

| Rule | Requirement |
|------|-------------|
| Minimal fields | A failure shows `name`, `file`, `line`, `message`. `--fields` adds more. `--full` lifts the message cut |
| Pre-computed aggregate | One `summary` line with counts and duration. The reader never adds up numbers |
| Definitive empty state | A passing run prints `failures: none` and `flaky: none`, never a blank |
| Truncation | Messages are cut at 200 characters with `… (N chars total)`. Stack traces are never inlined. `raw.stdout_path` is given, and `--full` prints the first lines of it |
| Failure limit | At most 20 failures, shown as `failures[20 of 134]`, with a `help` line to see the rest |
| Errors | `status: error` plus `error:` (the code) and a `help:` line |
| Next steps | `help` lines offer rerunning only the failures, and `doctor` when a reporter is missing |
| Combined run | With `--framework all`, the view starts with one `status:` line for the overall result, then one block per framework in the layout above, each headed by its framework name |
| Timeout | `status: timeout`, then `counts: unavailable` when counts are `null`, plus the test that was running when the process was killed if stdout identified it |

## 6. Behaviour

### 6.1 Detection

| Framework | Signals |
|-----------|---------|
| pytest | `pytest.ini`; `pyproject.toml` with `[tool.pytest...]`; `tox.ini` or `setup.cfg` with a pytest section; `conftest.py`; or `tests/` containing `test_*.py` |
| jest | `jest.config.*`; or `package.json` with a `jest` key, or `jest` in scripts or devDependencies |

If several match, `run` returns `error: ambiguous` unless `framework` is set. A full-stack repo that legitimately has both is expected, so there are three ways out, in order of preference:

1. Pin `framework` in config (section 7), so the choice is made once.
2. Pass `--framework all` to run each detected framework in turn and get a `CombinedResult` (4.4).
3. Pass `--framework <name>` for a single run.

A monorepo with one framework per package passes `cwd` per package.

### 6.2 Report sources

Each adapter reads the most stable machine-readable output the tool provides without non-standard plugins.

| Framework | Preferred report | Notes |
|-----------|------------------|-------|
| pytest | `--junitxml=<file>` (built in) | `pytest-json-report` may be used as an optional richer source |
| jest | `--json --outputFile=<file>` (built in) | |

**Verified by a live check (pytest 9.1.0):**

- The JUnit testcase element has `classname`, `name` and `time` only. It has **no `file` or `line` attribute**.
- The failure body is the traceback text, and it ends with a `path:line: ErrorType` line (for example `tests/test_x.py:3: AssertionError`). The adapter must extract `file` and `line` from that line, and fall back to `null` when it cannot.
- A collection error appears as a testcase with an `<error message="collection failure">` element and `classname=""`. The adapter must map it to `error: collection`, not to a failed test.
- pytest's own exit codes: `1` tests failed, `2` interrupted (collection error), `5` no tests collected. The adapter maps these onto its own statuses (`failed`, `error`, `error: no_tests`).

**Not yet verified (check before implementing each adapter):**

- jest: which `file` and `line` information the JSON provides, and whether `--testLocationInResults` is needed.
- jest: how `pending`, `todo`, `skipped` and `disabled` appear in the JSON, and how a suite that fails to load is reported (needed for the outcome mapping in 4.2).
- jest: whether `fullName` (ancestor titles joined by a space) is stable enough to build the `-t` pattern used for retries (6.4).
- pytest: how xfail, non-strict xpass and strict xpass appear in the JUnit XML. A live check is needed to confirm the mapping in 4.2.
- pytest and jest: which verbose flags make stdout progress parseable enough to give counts after a timeout (6.3).

If no machine-readable report can be produced, the adapter falls back to parsing stdout and sets `degraded = true`.

### 6.3 Execution

- Run as a child process in its own process group (POSIX) or process tree (Windows), with `cwd` and merged `env`. On Windows the child starts with `CREATE_NEW_PROCESS_GROUP`, and the tree is killed with `taskkill /T /F /PID <pid>`. On POSIX the group gets SIGTERM, then SIGKILL after the grace period.
- Capture stdout and stderr to a file. The cap is `max_output_bytes` (default 5 MiB); keep the tail.
- On timeout: send a terminate signal to the whole group or tree, wait `kill_grace_seconds` (default 5), then force-kill. Result `status = timeout`. Child processes of the test must be killed too.
- **Counts after a timeout.** pytest's `--junitxml` and jest's `--outputFile` are written at the end of a run, so a killed run normally leaves no report. The adapter therefore:
  1. Uses a report only if one exists and parses.
  2. Otherwise adds the verbose flags the framework needs and parses the stdout progress lines, setting `degraded = true`. Counts are lower bounds.
  3. Otherwise sets all counts to `null`.

  If stdout shows which test was running when the kill happened, a `warnings` entry names it, since that is usually the hanging test.
- Parallelism is translated per framework (`pytest -n N` if xdist is present, `jest --maxWorkers=N`). If the request cannot be honoured, the result carries a warning instead of failing.
- **Cross-platform:** v0.1.0 implements Linux, macOS and Windows (D20). CI tests Linux and macOS only. Windows has no automated test in v0.1.0, so its behaviour is not verified (tracked as a GitHub issue, "Windows testing"). Process-group signals are POSIX-only, so Windows uses its own mechanism (6.3). Paths use `pathlib`. Files are read and written as UTF-8. Both LF and CRLF line endings are handled in parsed output.

### 6.4 Subsets and retries

**Test names.** `failures[].name` and `flaky[].name` use one format per framework, and it is the format `select` accepts:

| Framework | Name format | Example |
|-----------|-------------|---------|
| pytest | pytest node ID | `tests/test_x.py::TestCart::test_add[3]` |
| jest | `<file relative to cwd, forward slashes>::<titles joined by " > ">` | `src/cart.test.js::Cart > adds item` |

**Selecting.**

- pytest: file paths or node IDs are passed as arguments.
- jest, file path: `--runTestsByPath <file>`.
- jest, `file::title` name: `--runTestsByPath <file> -t '^<escaped fullName>$'`, where `fullName` is the titles joined by a single space and regex-escaped. jest's `-t` applies to every selected file, so when name selectors target more than one file, the adapter runs one jest invocation per file and merges the results into one `TestResult`.
- Anything else returns `error: unsupported_selector` with the reason.

**Retrying.** `retry_failed: N` re-runs failures up to N times. A test that fails first and passes later is listed in `flaky` and does not count as failed. The final `status` reflects only tests that still fail. `retry_mode` sets what is re-run:

| Mode | What is re-run | Trade-off |
|------|----------------|-----------|
| `file` (default) | Every test file that contained a still-failing test, in full | Keeps in-file order and shared state, so an order-dependent failure is not reported as flaky. Costs more time |
| `isolated` | Only the failing tests, by node ID (pytest) or `-t` pattern (jest) | Fast. A test that fails in the suite because of order or shared state, but passes alone, is reported as `flaky` and the run exits 0. The caller opts into that risk |

- Only tests that failed earlier are judged on a retry. If a test that passed first fails during a `file` retry, it does not change `status`, but a `warnings` entry names it.
- Neither mode reproduces cross-file order. A failure caused by another file's state can still look flaky. That is why `flaky[].retry_mode` is recorded.
- A jest test whose title is not unique within its file cannot be selected by name. It is retried at file level whatever `retry_mode` says, and a `warnings` entry says so.

### 6.5 Coverage

When `coverage: true`: pytest via `--cov` and `--cov-report=json`; jest via `--coverage` with a json-summary reporter. The result carries `coverage.line_percent` and optional per-file figures. If coverage tooling is missing, `status` is unaffected, `coverage` is `null`, and a warning is added. Thresholds are applied by the caller.

## 7. Configuration

```toml
# test-adapters.toml
framework = "auto"             # auto | pytest | jest | all. Pin this in repos that have several frameworks
timeout_seconds = 600
kill_grace_seconds = 5
max_output_bytes = 5242880
parallelism = "auto"
require_tests = true           # status=error if zero tests were collected
retry_failed = 0
retry_mode = "file"            # file | isolated
coverage = false

[command_overrides]            # per framework: replace the generated command. Omit a key to keep the generated command
# pytest = "..."
```

Precedence: command-line flag, then environment, then config file, then default. The config file is `test-adapters.toml` in the working directory (or the `--cwd` directory). There is no fallback to `pyproject.toml`, because a jest-only repo has none (D18).

## 8. Failure Modes

| Situation | Behaviour |
|-----------|-----------|
| Framework binary absent | `status=error`, `error.code=tool_missing`, install hint, no crash |
| Collection error | `status=error`, `error.code=collection`, first error message |
| Zero tests and `require_tests` | `status=error`, `error.code=no_tests` |
| Report malformed or missing | `status=error`, `error.code=unparseable_report`, stdout path included; stdout fallback attempted first |
| Time limit exceeded | Process tree killed; `status=timeout`. Counts come from a report if one exists, else from stdout progress (`degraded=true`), else they are `null` |
| Several frameworks, none chosen | `status=error`, `error.code=ambiguous`; nothing is run. The message lists the detected frameworks and the ways to choose (6.1) |

The library defines its own typed errors and has no dependency on any error-handling library. A consumer may map `error.code` and `timeout` to its own vocabulary. Suggested recoverability: `timeout` is ambiguous (a retry may help); `tool_missing`, `no_tests` and `ambiguous` are permanent until configuration changes; `collection` and `unparseable_report` are permanent until the code or tool is fixed.

## 9. Acceptance Criteria

1. For each supported framework, a sample project with 3 pass / 1 fail / 1 skip yields identical `TestResult` counts and one failure with `file` and `line`.
2. A project with a collection error yields `status=error` and `error.code=collection`, not `failed`, and exits 3.
3. A hanging test is killed at the timeout, including child processes of the test. The run exits 4. Counts are `null` or come from stdout with `degraded=true`; they are never invented as `0`.
4. A test that fails once and then passes with `retry_failed: 1` is listed under `flaky` with its `retry_mode`, the run is `passed`, and the exit code is 0.
5. A toy adapter in the test suite proves a new framework can be added without changing existing code.
6. `parse` on recorded report fixtures gives the same output as `run` on the same project.
7. The default view of a passing run prints `failures: none` and `flaky: none` and exits 0. A failing run lists at most 20 failures with `n of total` and exits 1.
8. A failure message of 5,000 characters is cut in the default view, complete with `--full`, and always complete in `--json`.
9. `status: error` runs (tool missing, no tests) exit 3 and carry a typed `error:` and a `help:` line. An unknown flag exits 2 and names the valid flags.
10. Running with no arguments detects and checks the framework without executing any test.
11. `--result-file` writes the complete JSON result, including `flaky`, even when stdout shows the default view.
12. The `file` and `line` of a pytest failure come from the traceback, per section 6.2. If the traceback has no matching line, `line` is `null`.
13. The test suite passes on Linux and macOS in CI. Windows is implemented (6.3) but has no test job in v0.1.0 (D20). The README says "implemented, not tested on Windows". It does not say "verified" or "supported".
14. A sample project per framework containing an xfail (or jest todo), a non-strict xpass (pytest only) and a fixture-teardown error yields counts that match the mapping in 4.2 and satisfy `total = passed + failed + skipped + errors`.
15. With an order-dependent test (fails in the suite, passes alone), `retry_mode: file` leaves the run `failed`, and `retry_mode: isolated` reports it under `flaky` with `retry_mode: isolated` and exits 0. The difference is the documented trade-off, so it is tested.
16. A jest retry of one failing test uses the `-t` pattern and re-runs only that test. A jest file with two tests of the same title is retried at file level with a warning.
17. A repo with pytest and jest: no `framework` gives `error: ambiguous` and exit 3, with the message naming both frameworks and the options. `--framework all` returns a `CombinedResult` with two entries, and the exit code follows the worst status. One failing framework does not stop the other from running.
18. `--framework all` with `--select` returns `error: unsupported_selector`.
24. **Coverage.** With `coverage = true` and the coverage tooling installed, `coverage.line_percent` is a number. With the tooling missing, `status` is unaffected, `coverage` is `null`, and `warnings` names the missing tool.
25. **Parallelism.** With a `parallelism` request that cannot be honoured (for example, pytest with xdist absent), the run completes and `warnings` says the request was not honoured. The run does not fail.

### 9.1 Validation on real projects

Criteria 1 to 18 run against fixtures the implementer writes, so they cannot show that the tool is right on projects it was not built around. The criteria below use outside judges: the framework's own output, and an A/B comparison of agent runs. Numbers marked *(starting value)* are first targets, to be adjusted after the first run and then fixed.

**Corpus.** A list of open-source repositories, pinned to commit SHAs, in a file in this repo (for example `corpus/repos.yaml`). It is cloned in CI and never vendored. Starting value: 20 repos, 12 pytest and 8 jest, permissively licensed, including monorepos, xdist users, and projects with a custom `conftest.py` or reporter.

19. **Agreement with the framework.** On every corpus repo, `total`, `passed`, `failed`, `skipped` and `errors` equal the counts in the framework's own summary line, and the `status` and exit code agree with the framework's own exit code (using the mapping in 6.2). Bar: zero unexplained disagreements. Any residual difference must be a documented exception, backed by a fixture and an entry in `docs/` that explains the cause. Every disagreement is saved as a fixture before it is fixed.
20. **Mutation matrix.** For each corpus repo, apply each mutation to a scratch copy and run the tool. Every result must match the table, with no process left running afterwards.

    | Mutation | Expected status | Exit |
    |----------|-----------------|------|
    | One test with a failing assert | `failed`, with `file` and `line` | 1 |
    | One import error in a test module | `error`, `collection` | 3 |
    | One test that sleeps far past the limit and spawns a child process | `timeout`; the child is also dead | 4 |
    | One test that fails the first time and passes after (`retry_failed: 1`) | `passed`, listed in `flaky` | 0 |
    | One setup or teardown error in a fixture | `failed`, counted in `errors` | 1 |

21. **Platform and version matrix.** Criteria 19 and 20 run on Linux and macOS, with Python 3.11 and the latest release, against two major versions of each framework. Starting value: pytest 8 and 9, jest 29 and 30. Windows is not in this matrix in v0.1.0 (D20); its test job is the Windows testing issue. A combination that is not run is reported as not run, not as passing.
22. **Agent A/B (pilot).** The belief under test: the default view lowers the tokens an agent spends on test output without lowering its success rate. Method: 3 seeded bugs across corpus repos, each run by the same coding agent twice, once with the raw framework command and once with `test-adapters run`. That is 3 bugs × 2 arms = 6 sessions, plus 1 spare session for a run that fails for infrastructure reasons. Harness: Claude Code headless (`claude -p`) on the model the gateway gives, recorded for both arms. The gateway does not allow a model change, so the pilot records the model and does not set it. Hard cap: 7 sessions. Record tokens read from test output and turns to green. Fix rate is recorded, but 3 bugs cannot measure it, so it is reported as "not measured". The result is reported, not gated (D14). The 30-bug study is deferred to v0.2. The numbers are recorded in `docs/`. The agent harness is chosen by configuration, not fixed in code.
23. **Adoption.** The package installs with a single `pipx` or `uv tool` command, and ships a short snippet for an agent instruction file that tells the agent to run `test-adapters run` instead of calling the framework directly. A fresh agent session given only the snippet uses the tool on its first test run. This is checked by one headless Claude Code session, on the model the gateway gives, recorded as in the pilot, run outside the 7-session pilot cap after owner approval.

## 10. Defaults Taken

The following were decided, then confirmed or changed by the owner. Each can still be revisited.

| # | Default | Why |
|---|---------|-----|
| D1 | Python is the implementation language | Fits the frameworks' own tooling; subprocess and report parsing are simple |
| D2 | First release supports **pytest and jest only**. Cargo is deferred | Cargo needs nextest (an install) or nightly libtest JSON, which is unconfirmed. The adapter interface keeps it cheap to add later |
| D3 | Distinct exit codes 0/1/2/3/4 | A caller that reads only the exit code can tell a regression from a tooling fault or a timeout |
| D4 | `--result-file` flag | Lets exit-code-only callers retrieve `flaky` and failure detail |
| D5 | A flaky pass exits 0 | Flakiness is reported in data, not as a failure. Callers that want to fail on flakiness read `flaky` |
| D6 | JUnit and built-in JSON preferred over plugin reports | Fewer installation prerequisites |
| D7 | `error` is a distinct status from `failed` | A collection error is not a test failure and should not be blamed on a change in the same way |
| D8 | The no-argument command never runs tests | Running is slow and has side effects, so it is not a safe session-start action |
| D9 | After a timeout, counts are `null` when nothing is parseable, never `0` | Both reports are written at the end of a run, so a zero would read as "no tests ran" |
| D10 | xfail, todo and pending count as `skipped`; setup or teardown errors count as `errors` and make the run `failed` | Keeps the schema small. The verdict is unaffected by xfail and todo |
| D11 | `retry_mode` defaults to `file` | Retrying a single test alone can hide order-dependent failures, and D5 would then turn them into exit 0 |
| D12 | `framework: all` runs frameworks sequentially, and `error` outranks `failed` in the overall status | No resource contention. A framework with no trustworthy result means the repo is not known to be green |
| D13 | Real-project validation (9.1) is part of the definition of done for the first release | Fixture-only tests are graded by their author. The pytest `file` and `line` assumption was already wrong once |
| D14 | The agent A/B (criterion 22) is reported, not a release gate. Changed by the owner from the original gate | A 3-bug pilot cannot show a fix-rate difference, so a gate would pass or fail on chance. The token result is reported, and a missed target triggers a default-view tuning pass in v0.2 |
| D15 | The corpus lives in CI and is cloned, not vendored | Keeps the repo small and avoids license questions. The cost is that CI needs network access |
| D16 | Python 3.11 or later | `tomllib` in the standard library needs 3.11, so config needs no extra dependency. CI tests 3.11 and the latest release |
| D17 | Standard library only at runtime | Each runtime dependency is a possible version conflict in the environments the tool is installed into. Test dependencies are unrestricted |
| D18 | Config is `test-adapters.toml` in the working directory | TOML is read by the standard library. One file avoids a precedence rule between two config sources. A jest-only repo has no `pyproject.toml` |
| D19 | MIT license. Published to PyPI as `test-adapters` 0.1.0, installed with `pipx` or `uv tool` | The repo was public with no license. The PyPI name is free. Upload needs owner approval of the version and README |
| D20 | Windows is implemented in v0.1.0 but not tested | The owner has no way to test Windows, so no CI job runs it. The Windows code path (`CREATE_NEW_PROCESS_GROUP`, `taskkill /T`, CRLF handling) ships anyway, so it is ready when a test environment exists. README says "implemented, not tested on Windows". Testing is tracked as a GitHub issue, labelled `ready-for-human` |
| D21 | Coverage and parallelism are in v0.1.0 | Both are in the in-scope list. Criteria 24 and 25 cover them |
| D22 | CI runs on GitHub Actions in `plaktoz/test-adapters`, on Linux and macOS | Public repo, so runners are free |
| D23 | Done for v0.1.0: criteria 1–18, 24 and 25; criteria 19–21 on Linux and macOS with zero unexplained disagreements; criterion 23. Criterion 22 is a pilot report | Agreed in review. Criterion 22 is reported, not gated (D14) |

## 11. Open Questions

Resolved for v0.1.0:

1. Config file: `test-adapters.toml` in the working directory (D18).
2. Framework after pytest and jest: deferred to Phase 3 (roadmap), chosen by demand.
3. Cargo: deferred with item 2.
4. Packaging: published to PyPI as `test-adapters`, installed with `pipx` or `uv tool` (D19).
5. Corpus: 20 repos (12 pytest, 8 jest). A proposal with licenses and pinned SHAs goes to the owner for approval before anything is cloned.
6. A/B harness: Claude Code headless (`claude -p`), the model the gateway gives and records for both arms, 7 sessions at most (criterion 22). One adoption session runs outside that cap (criterion 23).
7. The A/B is reported, not a release gate (D14).
8. CI: GitHub Actions in `plaktoz/test-adapters`, Linux and macOS (D22). Windows is implemented but untested (D20).

Still open:

- Corpus list (item 5): waiting for owner approval of the proposal.
- Windows testing: tracked as a GitHub issue, blocked on a Windows test environment (D20).
