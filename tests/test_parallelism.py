"""T9 (issue #27): pytest parallelism through `pytest -n N` (requirements 6.3, criterion 25).

With xdist in the interpreter that runs the tests, `parallelism=N` adds `-n N`. Without it, the run
completes and `warnings` names xdist. `auto` adds no flag.

The xdist cases run only when pytest-xdist is installed:
    uvx --with pytest --with pytest-xdist pytest -q tests/test_parallelism.py
Without it they skip. The missing-tool cases simulate a missing xdist with `monkeypatch`, so they run
in both environments.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from test_adapters.adapters import pytest_adapter
from test_adapters.adapters.pytest_adapter import PytestAdapter
from test_adapters.model import Status, TestRequest, TestResult

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "pytest_cov"
HAS_XDIST = importlib.util.find_spec("xdist") is not None

JUNIT_ONE_PASS = (
    '<testsuite name="pytest" tests="1" failures="0" errors="0" skipped="0" time="0.01">'
    '<testcase classname="tests.test_calc" name="test_add" time="0.01"/></testsuite>'
)


def _argv(parallelism: int | str | None, workdir: Path) -> tuple[str, ...]:
    request = TestRequest(cwd=FIXTURE, framework="pytest", parallelism=parallelism)
    return PytestAdapter().build_command(request, workdir).argv


def test_auto_adds_no_xdist_flag(tmp_path: Path) -> None:
    assert "-n" not in _argv("auto", tmp_path)


def test_none_adds_no_xdist_flag(tmp_path: Path) -> None:
    assert "-n" not in _argv(None, tmp_path)


@pytest.mark.skipif(not HAS_XDIST, reason="pytest-xdist is not installed in this interpreter")
def test_int_adds_n_when_xdist_is_installed(tmp_path: Path) -> None:
    argv = _argv(2, tmp_path)
    i = argv.index("-n")
    assert argv[i + 1] == "2"


def test_int_with_xdist_missing_warns_and_does_not_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pytest_adapter, "_xdist_installed", lambda: False)
    assert "-n" not in _argv(2, tmp_path)

    result = _parse_one_pass(tmp_path, parallelism=2, monkeypatch=monkeypatch)

    assert result.status is Status.PASSED
    assert any("xdist" in w for w in result.warnings)


def test_int_with_xdist_present_has_no_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pytest_adapter, "_xdist_installed", lambda: True)
    result = _parse_one_pass(tmp_path, parallelism=2, monkeypatch=monkeypatch)

    assert result.status is Status.PASSED
    assert not any("xdist" in w for w in result.warnings)


def test_auto_has_no_xdist_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pytest_adapter, "_xdist_installed", lambda: False)
    result = _parse_one_pass(tmp_path, parallelism="auto", monkeypatch=monkeypatch)

    assert result.warnings == ()


def _parse_one_pass(tmp_path: Path, *, parallelism: int | str | None, monkeypatch: pytest.MonkeyPatch) -> TestResult:
    """Build the command, then parse a canned one-pass JUnit report as the run would leave it."""
    request = TestRequest(cwd=FIXTURE, framework="pytest", parallelism=parallelism)
    command = PytestAdapter().build_command(request, tmp_path)
    (tmp_path / "junit.xml").write_text(JUNIT_ONE_PASS, encoding="utf-8")
    return PytestAdapter().parse(list(command.report_paths), 0, "", False)
