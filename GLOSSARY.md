# test-adapters

A command-line tool and Python library that runs a project's tests with pytest or jest and returns one normalised result. Callers read one schema and one set of exit codes, not framework output.

## Running tests

**Framework**:
A test runner that test-adapters knows how to drive. v0.1.0 has two: pytest and jest.
_Avoid_: Tool, runner, engine

**Adapter**:
The component that detects one framework, builds its command, and parses its report into a TestResult.
_Avoid_: Plugin, driver, backend

**Selector**:
A file path or test name that narrows a run to some tests. Each framework has its own name format.
_Avoid_: Filter, pattern, path

**Test name**:
The identifier of one test in a result (`failures[].name`, `flaky[].name`). It is in the format that a Selector accepts.
_Avoid_: Test id, nodeid, title

## Results

**TestResult**:
The outcome of one run of one framework. It has one status, counts, failures, flaky tests, and optional coverage.
_Avoid_: Report, output, summary

**CombinedResult**:
The outcome of running every detected framework in turn. It holds one TestResult per framework and has its own overall status.
_Avoid_: Aggregate, merged result

**Status**:
The verdict of a TestResult or CombinedResult: `passed`, `failed`, `error`, or `timeout`.
_Avoid_: Result, outcome, state

**Failure**:
A test that still fails after all retries. It has a name, a message, and a file and line where they can be determined.
_Avoid_: Error (a Failure is a test result; an Error is a tooling fault)

**Error**:
A run that did not reach a trustworthy result, such as a missing framework or a collection error. It has a code and is reported with status `error`. Not to be confused with the `errors` count, which counts tests that failed in fixture setup or teardown.
_Avoid_: Failure, exception

**Error code**:
The typed reason for an Error: `tool_missing`, `collection`, `no_tests`, `unparseable_report`, `ambiguous`, or `unsupported_selector`.
_Avoid_: Error type, error kind

**Flaky test**:
A test that failed at least once and passed on a later attempt in the same run. It is recorded with the retry mode that produced the pass.
_Avoid_: Unstable, intermittent

**Degraded**:
A result whose counts were parsed from stdout because no machine-readable report was available. Its counts are best-effort lower bounds.
_Avoid_: Partial, approximate

## Retries

**Retry mode**:
What a retry re-runs. `file` re-runs every file that had a failure. `isolated` re-runs only the failing tests.
_Avoid_: Retry strategy, rerun policy

## Configuration and exit

**Config file**:
`test-adapters.toml` in the working directory. It is the only config file.
_Avoid_: Settings, rc file

**Exit code**:
The process result that tells a caller what happened: 0 passed, 1 failed, 2 usage error, 3 error, 4 timeout.
_Avoid_: Return code, status code
