"""T5 (issue #23): counts after a timeout come from `-v` progress lines, as lower bounds (requirements 6.3, D9).

A killed pytest run leaves no JUnit report. The adapter reads the `path::name STATUS` lines in stdout.
The counts are lower bounds, so `degraded` is true. With no parseable line, all counts stay null and
are never 0. The test that was running at the kill is named in `warnings`.

The stdout excerpts below were captured from pytest 9.2.0 (docs/live-checks/pytest-timeout-progress.md).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from test_adapters.adapters.pytest_adapter import PytestAdapter
from test_adapters.model import Status, TestRequest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "pytest_hang_progress"

# Real output of a killed run: 2 passed, 1 skipped, 1 failed, then test_hangs was running.
KILLED_STDOUT = (
    "============================= test session starts ==============================\n"
    "collecting ... collected 5 items\n"
    "\n"
    "tests/test_progress.py::test_pass_one PASSED                             [ 20%]\n"
    "tests/test_progress.py::test_pass_two PASSED                             [ 40%]\n"
    "tests/test_progress.py::test_skipped SKIPPED (skipped on purpose)        [ 60%]\n"
    "tests/test_progress.py::test_fails FAILED                                [ 80%]\n"
    "tests/test_progress.py::test_hangs "
)


def _timed_out(stdout: str):  # noqa: ANN202
    return PytestAdapter().parse([], None, stdout, True)


def test_progress_lines_give_lower_bound_counts_and_degraded() -> None:
    result = _timed_out(KILLED_STDOUT)

    assert result.status is Status.TIMEOUT
    assert (result.passed, result.failed, result.skipped, result.errors) == (2, 1, 1, 0)
    assert result.total == 4  # the running test is not counted: its outcome is not known
    assert result.degraded is True


def test_running_test_is_named_in_warnings() -> None:
    result = _timed_out(KILLED_STDOUT)

    assert any("tests/test_progress.py::test_hangs" in w for w in result.warnings)


def test_no_progress_lines_gives_null_counts_never_zero() -> None:
    result = _timed_out("============ test session starts ============\ncollecting ... ")

    assert result.status is Status.TIMEOUT
    assert (result.total, result.passed, result.failed, result.skipped, result.errors) == (None,) * 5
    assert result.degraded is False


def test_empty_stdout_gives_null_counts() -> None:
    result = _timed_out("")

    assert result.total is None
    assert result.degraded is False


def test_a_test_with_a_teardown_error_is_counted_once() -> None:
    # Real output: the test prints PASSED, then ERROR. The worst status wins, so it counts once (issue #42).
    stdout = (
        "tests/test_p.py::test_ok PASSED                                          [ 33%]\n"
        "tests/test_p.py::test_err PASSED                                         [ 66%]\n"
        "tests/test_p.py::test_err ERROR                                          [ 66%]\n"
        "tests/test_p.py::test_last "
    )
    result = _timed_out(stdout)

    assert (result.passed, result.errors, result.total) == (1, 1, 2)


def test_ids_with_spaces_and_xfail_parse() -> None:
    stdout = (
        "tests/test_p.py::test_param[a b] PASSED                                  [ 20%]\n"
        "tests/test_p.py::test_xf XFAIL (x)                                       [ 60%]\n"
        "tests/test_p.py::test_last "
    )
    result = _timed_out(stdout)

    assert (result.passed, result.skipped, result.total) == (1, 1, 2)  # xfail counts as skipped (4.2)


def test_a_finished_last_line_names_no_running_test() -> None:
    stdout = "tests/test_p.py::test_ok PASSED                                          [100%]\n"
    result = _timed_out(stdout)

    assert result.passed == 1
    assert result.warnings == ()


def test_build_command_asks_for_progress_lines() -> None:
    command = PytestAdapter().build_command(TestRequest(cwd=FIXTURE, framework="pytest"), Path("/tmp/x"))

    assert "-v" in command.argv
    assert "-q" not in command.argv  # -q cancels -v and leaves only the dot form


def test_cli_timeout_on_a_real_hang_reports_lower_bound_counts(tmp_path: Path) -> None:
    import json

    out = tmp_path / "result.json"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    proc = subprocess.run(
        [sys.executable, "-m", "test_adapters.cli", "run", "--timeout", "3", "--result-file", str(out)],
        cwd=FIXTURE,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert proc.returncode == 4, proc.stdout + proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["status"] == "timeout"
    assert (data["passed"], data["failed"], data["skipped"]) == (2, 1, 1)
    assert data["degraded"] is True
    assert any("test_hangs" in w for w in data["warnings"])
