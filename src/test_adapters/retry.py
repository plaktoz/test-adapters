"""Retries for failing tests (requirements 6.4, 4.2; decisions D5 and D11).

Pure logic, no I/O. The caller passes `rerun`, which runs the framework on a selection and
returns its TestResult. This module decides what each retry selects and how the attempts fold
into one result.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace

from test_adapters.model import Failure, FlakyTest, RetryMode, Status, TestResult

Rerun = Callable[[tuple[str, ...]], TestResult]


def with_retries(first: TestResult, rerun: Rerun, retries: int, mode: RetryMode) -> TestResult:
    """Re-run the still-failing tests up to `retries` times and fold the attempts into one result.

    `first` is the run the caller asked for. Only its failures are retried. `file` mode selects
    every file that holds a still-failing test. `isolated` mode selects only the failing node IDs.
    A test that failed and then passed is `flaky` and is counted as passed (4.2). A test that
    passed first and fails on a retry adds one warning and does not change status (6.4).
    """
    if retries <= 0 or first.status is not Status.FAILED or not first.failures:
        return first
    if first.passed is None or first.failed is None or first.errors is None:  # narrows for mypy; a FAILED result has counts
        return first

    order = [f.name for f in first.failures]  # first-run failure order, for stable output
    pending: dict[str, Failure] = {f.name: f for f in first.failures}
    passed_on: dict[str, int] = {}  # name -> attempt on which it first passed
    warnings: list[str] = list(first.warnings)
    warned: set[str] = set()
    errors_warned = False
    duration_ms = first.duration_ms

    for attempt in range(2, retries + 2):  # attempt 1 is `first`
        result = rerun(_selection(list(pending.values()), mode))
        duration_ms += result.duration_ms
        if result.status not in (Status.PASSED, Status.FAILED):
            warnings.append(f"retry {attempt - 1} did not finish ({result.status.value}); the earlier result is reported")
            break

        if result.errors:
            # An error outside a test body (4.2, fixture teardown) has no named failure, so the
            # retry cannot show which pending test passed. No pending test is judged passed on it.
            if not errors_warned:
                errors_warned = True
                warnings.append(f"a {mode.value} retry reported errors outside test bodies; no test was judged passed on it")
            continue

        failing = {f.name: f for f in result.failures}
        for name in list(pending):
            if name in failing:
                pending[name] = failing[name]
            else:
                passed_on[name] = attempt
                del pending[name]
        for name in failing:
            if name not in pending and name not in warned:  # not judged as still failing: it passed before
                warned.add(name)
                warnings.append(f"{name} passed earlier and failed on a {mode.value} retry; status is not changed")
        if not pending:
            break

    flaky = tuple(FlakyTest(name=name, attempts=passed_on[name], retry_mode=mode) for name in order if name in passed_on)
    failures = tuple(pending[name] for name in order if name in pending)
    failed = first.failed - len(flaky)
    passed = first.passed + len(flaky)
    status = Status.FAILED if failed or first.errors else Status.PASSED
    return replace(
        first,
        status=status,
        passed=passed,
        failed=failed,
        failures=failures,
        flaky=flaky,
        warnings=tuple(warnings),
        duration_ms=duration_ms,
    )


def _selection(pending: Sequence[Failure], mode: RetryMode) -> tuple[str, ...]:
    """What one retry runs: the failing node IDs (isolated), or each file holding one (file).

    The file comes from `Failure.file` when the traceback named one. Otherwise it is the part of
    the node ID before the first `::`.
    """
    if mode is RetryMode.ISOLATED:
        return tuple(f.name for f in pending)
    files: dict[str, None] = {}  # an ordered set
    for f in pending:
        files[f.file or f.name.split("::", 1)[0]] = None
    return tuple(files)
