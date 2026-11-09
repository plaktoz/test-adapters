"""T2 (issue #20): pytest coverage through `coverage=True` (requirements 6.5, 4.2, criterion 24).

Fixture `tests/fixtures/pytest_cov/`: one passing test. `calc.subtract` is never called, so the
file is covered in part.

The pytest-cov cases run only when pytest-cov is in the interpreter that runs the tests:
    uvx --with pytest --with pytest-cov pytest -q tests/test_coverage.py
Without pytest-cov they skip. The missing-tool cases use `monkeypatch` to simulate a missing
pytest-cov, so they run in both environments.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from test_adapters import api
from test_adapters.adapters import pytest_adapter
from test_adapters.adapters.pytest_adapter import PytestAdapter
from test_adapters.model import Status, TestRequest
from test_adapters.render import json_view

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "pytest_cov"
HAS_PYTEST_COV = importlib.util.find_spec("pytest_cov") is not None

JUNIT_ONE_PASS = (
    '<testsuite name="pytest" tests="1" failures="0" errors="0" skipped="0" time="0.01">'
    '<testcase classname="tests.test_calc" name="test_add" time="0.01"/></testsuite>'
)


def _request(*, coverage: bool) -> TestRequest:
    return TestRequest(cwd=FIXTURE, framework="pytest", coverage=coverage)


def _simulate_pytest_cov(monkeypatch: pytest.MonkeyPatch, installed: bool) -> None:
    monkeypatch.setattr(pytest_adapter, "_pytest_cov_installed", lambda: installed)


@pytest.mark.skipif(not HAS_PYTEST_COV, reason="pytest-cov is not installed in this interpreter")
def test_line_percent_is_a_number_when_pytest_cov_is_installed():
    result = api.run(_request(coverage=True))
    assert result.status is Status.PASSED, result
    assert result.warnings == ()
    assert result.coverage is not None
    line_percent = result.coverage.line_percent
    assert isinstance(line_percent, float)
    assert 0.0 <= line_percent <= 100.0
    per_file = {f.path: f.line_percent for f in result.coverage.files}
    assert 0.0 < per_file["calc.py"] < 100.0  # subtract() is never called


@pytest.mark.skipif(not HAS_PYTEST_COV, reason="pytest-cov is not installed in this interpreter")
def test_coverage_does_not_change_the_counts_when_pytest_cov_is_installed():
    baseline = api.run(_request(coverage=False))
    result = api.run(_request(coverage=True))
    assert result.status is baseline.status
    assert (result.total, result.passed, result.failed, result.skipped, result.errors) == (
        baseline.total,
        baseline.passed,
        baseline.failed,
        baseline.skipped,
        baseline.errors,
    )


def test_missing_pytest_cov_gives_null_coverage_and_names_the_tool(monkeypatch: pytest.MonkeyPatch):
    _simulate_pytest_cov(monkeypatch, installed=False)
    result = api.run(_request(coverage=True))
    assert result.coverage is None
    assert any("pytest-cov" in w for w in result.warnings), result.warnings


def test_missing_pytest_cov_leaves_the_status_and_counts_unchanged(monkeypatch: pytest.MonkeyPatch):
    baseline = api.run(_request(coverage=False))
    _simulate_pytest_cov(monkeypatch, installed=False)
    result = api.run(_request(coverage=True))
    assert result.status is baseline.status is Status.PASSED
    assert result.error is None
    assert (result.total, result.passed, result.failed, result.skipped, result.errors) == (
        baseline.total,
        baseline.passed,
        baseline.failed,
        baseline.skipped,
        baseline.errors,
    )


def test_coverage_off_adds_no_coverage_flags_and_no_state_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _simulate_pytest_cov(monkeypatch, installed=False)
    command = PytestAdapter().build_command(_request(coverage=False), tmp_path)
    assert not any(arg.startswith("--cov") for arg in command.argv)
    assert all(p.name != pytest_adapter._COVERAGE_STATE for p in command.report_paths)
    assert "COVERAGE_FILE" not in command.env


def test_build_command_adds_the_pytest_cov_flags_when_installed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _simulate_pytest_cov(monkeypatch, installed=True)
    command = PytestAdapter().build_command(_request(coverage=True), tmp_path)
    assert "--cov" in command.argv
    assert f"--cov-report=json:{tmp_path / pytest_adapter._COVERAGE_JSON}" in command.argv
    # The data file goes to the work directory, not into the project being measured.
    assert command.env["COVERAGE_FILE"] == str(tmp_path / ".coverage")
    assert (tmp_path / pytest_adapter._COVERAGE_STATE).read_text(encoding="utf-8") == "installed"


def test_build_command_records_the_missing_tool_when_not_installed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _simulate_pytest_cov(monkeypatch, installed=False)
    command = PytestAdapter().build_command(_request(coverage=True), tmp_path)
    assert not any(arg.startswith("--cov") for arg in command.argv)
    assert (tmp_path / pytest_adapter._COVERAGE_STATE).read_text(encoding="utf-8") == "missing"


def test_parse_reads_line_percent_and_file_figures_from_the_coverage_json(tmp_path: Path):
    junit = tmp_path / "junit.xml"
    junit.write_text(JUNIT_ONE_PASS, encoding="utf-8")
    state = tmp_path / pytest_adapter._COVERAGE_STATE
    state.write_text("installed", encoding="utf-8")
    cov = tmp_path / pytest_adapter._COVERAGE_JSON
    cov.write_text(
        json.dumps(
            {
                "files": {"calc.py": {"summary": {"percent_covered": 75.0}}},
                "totals": {"percent_covered": 75.0},
            }
        ),
        encoding="utf-8",
    )
    result = PytestAdapter().parse([state, junit, cov], exit_code=0, stdout="", timed_out=False)
    assert result.status is Status.PASSED
    assert result.coverage is not None
    assert result.coverage.line_percent == 75.0
    assert [(f.path, f.line_percent) for f in result.coverage.files] == [("calc.py", 75.0)]
    assert result.warnings == ()


def test_parse_names_the_missing_tool_and_keeps_the_status(tmp_path: Path):
    junit = tmp_path / "junit.xml"
    junit.write_text(JUNIT_ONE_PASS, encoding="utf-8")
    (tmp_path / pytest_adapter._COVERAGE_STATE).write_text("missing", encoding="utf-8")
    result = PytestAdapter().parse(
        [junit, tmp_path / pytest_adapter._COVERAGE_STATE], exit_code=0, stdout="", timed_out=False
    )
    assert result.status is Status.PASSED
    assert result.coverage is None
    assert len(result.warnings) == 1 and "pytest-cov" in result.warnings[0]


def test_unreadable_coverage_report_gives_null_coverage_and_a_warning(tmp_path: Path):
    junit = tmp_path / "junit.xml"
    junit.write_text(JUNIT_ONE_PASS, encoding="utf-8")
    (tmp_path / pytest_adapter._COVERAGE_STATE).write_text("installed", encoding="utf-8")
    cov = tmp_path / pytest_adapter._COVERAGE_JSON
    cov.write_text("{not json", encoding="utf-8")
    result = PytestAdapter().parse(
        [junit, tmp_path / pytest_adapter._COVERAGE_STATE, cov], exit_code=0, stdout="", timed_out=False
    )
    assert result.status is Status.PASSED
    assert result.coverage is None
    assert len(result.warnings) == 1 and "coverage" in result.warnings[0]


def test_installed_but_no_coverage_report_gives_null_coverage_and_a_warning(tmp_path: Path):
    junit = tmp_path / "junit.xml"
    junit.write_text(JUNIT_ONE_PASS, encoding="utf-8")
    (tmp_path / pytest_adapter._COVERAGE_STATE).write_text("installed", encoding="utf-8")
    result = PytestAdapter().parse(
        [junit, tmp_path / pytest_adapter._COVERAGE_STATE], exit_code=0, stdout="", timed_out=False
    )
    assert result.status is Status.PASSED
    assert result.coverage is None
    assert len(result.warnings) == 1 and "coverage" in result.warnings[0]


@pytest.mark.skipif(not HAS_PYTEST_COV, reason="pytest-cov is not installed in this interpreter")
def test_json_view_carries_coverage_line_percent_as_a_number():
    result = api.run(_request(coverage=True))
    data = json.loads(json_view(result))
    assert isinstance(data["coverage"]["line_percent"], float)
    assert data["coverage"]["line_percent"] == result.coverage.line_percent
