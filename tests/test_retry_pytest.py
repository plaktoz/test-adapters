"""pytest retries (requirements 6.4, 4.2, 9 criteria 4 and 15, decisions D5 and D11).

Seam: `api.run` with `retry_failed` and `retry_mode`, on the fixtures in `tests/fixtures/pytest_flaky/`.
Each fixture writes its attempt markers and run log to `FIXTURE_STATE_DIR`, which is a fresh
directory per test, so the fixture projects themselves are never changed.
"""

from __future__ import annotations

import json
from pathlib import Path

from test_adapters.api import run
from test_adapters.combine import exit_code_for
from test_adapters.model import FlakyTest, RetryMode, Status, TestRequest, TestResult
from test_adapters.render import json_view

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "pytest_flaky"


def _run(project: str, state: Path, *, retry_failed: int, retry_mode: RetryMode = RetryMode.FILE) -> TestResult:
    state.mkdir(parents=True, exist_ok=True)
    request = TestRequest(
        cwd=FIXTURES / project,
        framework="pytest",
        retry_failed=retry_failed,
        retry_mode=retry_mode,
        env={"FIXTURE_STATE_DIR": str(state)},
    )
    return run(request)


def _runs(state: Path) -> list[str]:
    """Every test body that ran, in order, across the first run and all retries."""
    log = state / "runs.log"
    return log.read_text(encoding="utf-8").split() if log.exists() else []


def test_fails_then_passes_is_flaky_and_the_run_passes(tmp_path: Path):
    # Criterion 4: fails on attempt 1, passes on attempt 2.
    result = _run("flaky_once", tmp_path / "state", retry_failed=1)
    assert result.status is Status.PASSED
    assert exit_code_for(result.status) == 0
    assert result.flaky == (FlakyTest(name="tests/test_flaky_once.py::test_flaky_once", attempts=2, retry_mode=RetryMode.FILE),)
    assert (result.total, result.passed, result.failed) == (1, 1, 0)
    assert result.failures == ()


def test_flaky_entry_has_the_wire_shape_of_4_2(tmp_path: Path):
    result = _run("flaky_once", tmp_path / "state", retry_failed=1)
    wire = json.loads(json_view(result))
    assert wire["status"] == "passed"
    assert wire["flaky"] == [{"name": "tests/test_flaky_once.py::test_flaky_once", "attempts": 2, "retry_mode": "file"}]


def test_no_retry_by_default(tmp_path: Path):
    result = _run("flaky_once", tmp_path / "state", retry_failed=0)
    assert result.status is Status.FAILED
    assert result.flaky == ()


def test_always_failing_test_is_retried_n_times_and_stays_failed(tmp_path: Path):
    state = tmp_path / "state"
    result = _run("always_fails", state, retry_failed=2)
    assert result.status is Status.FAILED
    assert exit_code_for(result.status) == 1
    assert result.flaky == ()
    assert [f.name for f in result.failures] == ["tests/test_always_fails.py::test_always_fails"]
    assert _runs(state) == ["always_fails"] * 3  # the first run and two retries


def test_order_dependent_test_stays_failed_in_file_mode(tmp_path: Path):
    # Criterion 15, file mode: the whole file re-runs, so test_a runs before test_b again.
    state = tmp_path / "state"
    result = _run("order", state, retry_failed=1, retry_mode=RetryMode.FILE)
    assert result.status is Status.FAILED
    assert exit_code_for(result.status) == 1
    assert result.flaky == ()
    assert [f.name for f in result.failures] == ["tests/test_order.py::test_b_fails_after_a"]
    assert _runs(state) == ["a", "b", "a", "b"]


def test_order_dependent_test_is_flaky_in_isolated_mode(tmp_path: Path):
    # Criterion 15, isolated mode: only the failing node ID re-runs, so test_b runs alone and passes.
    state = tmp_path / "state"
    result = _run("order", state, retry_failed=1, retry_mode=RetryMode.ISOLATED)
    assert result.status is Status.PASSED
    assert exit_code_for(result.status) == 0
    assert result.flaky == (
        FlakyTest(name="tests/test_order.py::test_b_fails_after_a", attempts=2, retry_mode=RetryMode.ISOLATED),
    )
    assert result.failures == ()
    assert _runs(state) == ["a", "b", "b"]


def test_test_that_passed_first_and_fails_on_retry_warns_only(tmp_path: Path):
    # The file retry fails test_passes_then_fails, which passed the first time. It adds a warning and
    # does not change status. test_fails_once is the only failure the retry judges, and it passes.
    result = _run("warn", tmp_path / "state", retry_failed=1, retry_mode=RetryMode.FILE)
    assert result.status is Status.PASSED
    assert exit_code_for(result.status) == 0
    assert result.flaky == (FlakyTest(name="tests/test_warn.py::test_fails_once", attempts=2, retry_mode=RetryMode.FILE),)
    assert result.failures == ()
    assert len(result.warnings) == 1
    assert "tests/test_warn.py::test_passes_then_fails" in result.warnings[0]
