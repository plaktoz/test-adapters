"""pytest outcome mapping (requirements 4.2, 9.1 criterion 14, decision D10).

Seam: `PytestAdapter.parse` on a real JUnit report. The report comes from running pytest
on a fixture project under `tests/fixtures/pytest_outcomes/`:
- `tests/`: one case per outcome (plain pass, xfail, non-strict xpass, strict xpass, teardown error).
- `teardown_only/`: a body that passes and a teardown that errors, with nothing else to fail the run.

Expected counts are written out by hand from the 4.2 table, not computed from the adapter.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_adapters.adapters.pytest_adapter import PytestAdapter
from test_adapters.model import Status, TestResult

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "pytest_outcomes"


def run_fixture(project: Path, workdir: Path) -> TestResult:
    report = workdir / "junit.xml"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", f"--junitxml={report}"],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    # Each fixture project has a failing or erroring test on purpose, so pytest exits 1.
    assert proc.returncode == 1, proc.stdout + proc.stderr
    return PytestAdapter().parse([report], exit_code=proc.returncode, stdout=proc.stdout, timed_out=False)


def test_counts_match_the_4_2_mapping(tmp_path: Path):
    # plain pass -> passed, non-strict xpass -> passed (2)
    # strict xpass -> failed (1); xfail -> skipped (1); teardown error -> errors (1)
    result = run_fixture(FIXTURES, tmp_path)
    assert (result.total, result.passed, result.failed, result.skipped, result.errors) == (5, 2, 1, 1, 1)
    assert result.total == result.passed + result.failed + result.skipped + result.errors


def test_teardown_error_alone_makes_the_run_failed(tmp_path: Path):
    # 4.2: errors > 0 makes status failed, even though the test body passed.
    result = run_fixture(FIXTURES / "teardown_only", tmp_path)
    assert (result.total, result.passed, result.failed, result.skipped, result.errors) == (1, 0, 0, 0, 1)
    assert result.errors > 0
    assert result.status is Status.FAILED
    assert result.error is None
