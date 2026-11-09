"""Walking skeleton (Phase 4 step 3): one real pytest project, end to end.

Path: detect -> run -> parse -> text view -> exit code. Each assertion maps to a spec
criterion named in the test. Runs the real CLI in a subprocess, on a fixture that has
3 passing, 1 failing and 1 skipped test (criterion 1).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "pytest_mixed"


def cli(*args: str, cwd: Path = FIXTURE) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", "test_adapters.cli", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_run_default_view_reports_the_counts_and_failure():
    # Criterion 1 (counts, one failure with file and line) and criterion 7 (default view).
    proc = cli("run")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "status: failed" in proc.stdout
    assert "summary: 3 passed, 1 failed, 1 skipped of 5" in proc.stdout
    assert "test_fails" in proc.stdout
    assert "tests/test_mixed.py" in proc.stdout
    assert "tests/test_mixed.py,17," in proc.stdout  # line of the failing assert, from the traceback (criterion 12)


def test_run_json_is_the_complete_result(tmp_path: Path):
    # Criterion 11: --result-file writes the complete JSON, including flaky.
    out = tmp_path / "result.json"
    proc = cli("run", "--json", "--result-file", str(out))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["framework"] == "pytest"
    assert data["status"] == "failed"
    assert (data["total"], data["passed"], data["failed"], data["skipped"], data["errors"]) == (5, 3, 1, 1, 0)
    assert data["flaky"] == []
    assert data["failures"][0]["file"] == "tests/test_mixed.py"
    assert data["failures"][0]["line"] == 17  # the failing `assert 1 == 2` in test_mixed.py
    assert data["degraded"] is False


def test_detect_runs_nothing_and_finds_pytest():
    # Criterion 10: no-argument mode detects and checks, without running a test.
    proc = cli()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "pytest" in proc.stdout
    assert "summary:" not in proc.stdout  # no test run happened


def test_parse_matches_run_on_the_same_project(tmp_path: Path):
    # Criterion 6: parse on the recorded report gives the same counts as run.
    # The fixture has one failing test, so parse exits 1 like run does (5.4).
    report = tmp_path / "junit.xml"
    subprocess.run(
        [sys.executable, "-m", "pytest", "-q", f"--junitxml={report}"],
        cwd=FIXTURE,
        capture_output=True,
        check=False,
    )
    run_json = json.loads(cli("run", "--json").stdout)
    parse_proc = cli("parse", "pytest", str(report), "--json")
    assert parse_proc.returncode == 1, parse_proc.stdout + parse_proc.stderr
    parsed = json.loads(parse_proc.stdout)
    for key in ("total", "passed", "failed", "skipped", "errors", "status"):
        assert parsed[key] == run_json[key], key


@pytest.mark.parametrize("bad", ["--no-such-flag"])
def test_unknown_flag_is_a_usage_error(bad: str):
    # Criterion 9: unknown flag exits 2 and names the valid flags.
    proc = cli("run", bad)
    assert proc.returncode == 2
    assert "--framework" in proc.stderr
