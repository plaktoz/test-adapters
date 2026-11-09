"""pytest adapter (requirements 6.1, 6.2, 6.4, 6.5).

Walking-skeleton scope: detection, a plain run, and JUnit XML parsing for the pass, fail and
skip counts, with file and line taken from the traceback. Coverage through pytest-cov (6.5) is
built. Timeout counts, retries and xdist are not in the skeleton yet.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence

from test_adapters.adapters.base import Command
from test_adapters.errors import UsageError
from test_adapters.model import (
    Coverage,
    CoverageFile,
    ErrorCode,
    ErrorInfo,
    Failure,
    RawInfo,
    Status,
    TestRequest,
    TestResult,
)

_TRACE_LINE = re.compile(r"^(?P<file>[^\s:>E]\S*?):(?P<line>\d+): (?P<type>\w+)", re.MULTILINE)
_PYTEST_CONFIG_FILES = ("pytest.ini", "conftest.py")
# Work-directory files that carry coverage between build_command and parse. They ride in
# `Command.report_paths`, so parse must skip them when it looks for the JUnit report.
_COVERAGE_STATE = "coverage-state.txt"  # "installed" or "missing"
_COVERAGE_JSON = "coverage.json"  # written by pytest-cov's json report
_COVERAGE_FILES = (_COVERAGE_STATE, _COVERAGE_JSON)
_MISSING_PYTEST_COV = "pytest-cov is not installed in the interpreter that runs the tests, so coverage was not measured"


class PytestAdapter:
    name = "pytest"
    command_template = "pytest --junitxml={report} {select}"
    report_format = "junit-xml"

    def detect(self, cwd: Path) -> bool:
        """pytest.ini, pyproject [tool.pytest*], tox.ini/setup.cfg pytest section, conftest.py, or tests/test_*.py."""
        if any((cwd / f).is_file() for f in _PYTEST_CONFIG_FILES):
            return True
        pyproject = cwd / "pyproject.toml"
        if pyproject.is_file() and "[tool.pytest" in pyproject.read_text(encoding="utf-8"):
            return True
        return any(cwd.glob("tests/test_*.py"))

    def build_command(self, request: TestRequest, workdir: Path) -> Command:
        """`--junitxml=<file>`; selectors are node IDs or file paths passed as arguments.

        With `coverage`, `--cov` and a JSON report go to the work directory. pytest-cov is looked up
        in the interpreter that runs the tests. If it is missing, the command runs without coverage
        and parse adds a warning (6.5).
        """
        if request.parallelism not in ("auto", None):
            raise UsageError("walking skeleton does not support parallelism yet")
        report = workdir / "junit.xml"
        argv: list[str] = [sys.executable, "-m", "pytest", "-q", f"--junitxml={report}"]
        env: dict[str, str] = dict(request.env)
        report_paths: list[Path] = [report]
        if request.coverage:
            state = workdir / _COVERAGE_STATE
            report_paths.append(state)
            if _pytest_cov_installed():
                state.write_text("installed", encoding="utf-8")
                # The coverage data file goes to the work directory, not into the measured project.
                env["COVERAGE_FILE"] = str(workdir / ".coverage")
                argv += ["--cov", f"--cov-report=json:{workdir / _COVERAGE_JSON}"]
                report_paths.append(workdir / _COVERAGE_JSON)
            else:
                state.write_text("missing", encoding="utf-8")
        argv += list(request.select)
        return Command(argv=tuple(argv), env=env, report_paths=tuple(report_paths))

    def parse(self, report_files: Sequence[Path], exit_code: int | None, stdout: str, timed_out: bool) -> TestResult:
        """JUnit XML first. file and line come from the traceback's `path:line: ErrorType` line (6.2).

        Coverage, when requested, is read from the JSON report. A missing tool or an unreadable report
        leaves `coverage` null and adds a warning. The status and the counts do not change (6.5).
        """
        coverage, warnings = _coverage(report_files)
        report = next((p for p in report_files if p.is_file() and p.name not in _COVERAGE_FILES), None)
        if report is None:
            if timed_out:
                return _timeout(exit_code=exit_code, warnings=warnings)
            return _error(
                ErrorCode.UNPARSEABLE_REPORT,
                "no JUnit report was written",
                stdout_hint=True,
                exit_code=exit_code,
                warnings=warnings,
            )
        try:
            root = ET.parse(report).getroot()
        except ET.ParseError as exc:
            return _error(
                ErrorCode.UNPARSEABLE_REPORT,
                f"JUnit report is malformed: {exc}",
                stdout_hint=True,
                exit_code=exit_code,
                warnings=warnings,
            )

        suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
        cases = [case for suite in suites for case in suite.iter("testcase")]
        failures: list[Failure] = []
        passed = failed = skipped = errors = 0
        for case in cases:
            classname = case.get("classname", "")
            name = f"{classname}::{case.get('name', '')}"
            if case.find("error") is not None:
                if case.get("classname", "") == "":
                    # Collection error (4.3): the suite did not load.
                    return _error(
                        ErrorCode.COLLECTION,
                        case.get("name", "collection failed"),
                        stdout_hint=False,
                        exit_code=exit_code,
                        warnings=warnings,
                    )
                errors += 1
            elif case.find("failure") is not None:
                failed += 1
                body = case.find("failure")
                assert body is not None
                text = (body.text or "") + "\n" + (body.get("message") or "")
                file, line = _location(text)
                node = _node_id(file, classname, case.get("name", "")) if file else name
                failures.append(Failure(name=node, message=body.get("message") or "", file=file, line=line))
            elif case.find("skipped") is not None:
                skipped += 1
            else:
                passed += 1

        total = passed + failed + skipped + errors
        if total == 0:
            # A report with no test cases: nothing ran, so the repo is not known to be green (6.2).
            return _error(
                ErrorCode.NO_TESTS,
                "the report contains no test cases",
                stdout_hint=False,
                exit_code=exit_code,
                warnings=warnings,
            )
        status = Status.FAILED if (failed or errors) else Status.PASSED
        duration_ms = int(round(sum(float(s.get("time", "0")) for s in suites) * 1000))
        return TestResult(
            framework="pytest",
            status=status,
            error=None,
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            duration_ms=duration_ms,
            failures=tuple(failures),
            flaky=(),
            coverage=coverage,
            warnings=warnings,
            degraded=False,
            raw=RawInfo(exit_code=exit_code, stdout_path=None, report_path=str(report)),
            command="pytest",
        )

    def requires(self) -> Sequence[str]:
        """The `pytest` module, importable by the interpreter that runs `build_command`."""
        return ("pytest",)


def _node_id(file: str, classname: str, name: str) -> str:
    """`path::Class::test`, the form `pytest <nodeid>` accepts. JUnit gives a dotted module path instead."""
    module = file[:-3].replace("/", ".") if file.endswith(".py") else ""
    rest = classname[len(module) :].lstrip(".") if module and classname.startswith(module) else ""
    parts = [file, *([rest] if rest else []), name]
    return "::".join(parts)


def _location(text: str) -> tuple[str | None, int | None]:
    """The last `path:line: ErrorType` line in a traceback (6.2). None when absent."""
    matches = list(_TRACE_LINE.finditer(text))
    if not matches:
        return None, None
    last = matches[-1]
    return last.group("file"), int(last.group("line"))


def _pytest_cov_installed() -> bool:
    """True when pytest-cov can be imported by the interpreter that runs the tests (6.5)."""
    return importlib.util.find_spec("pytest_cov") is not None


def _coverage(report_files: Sequence[Path]) -> tuple[Coverage | None, tuple[str, ...]]:
    """Coverage and warnings from the coverage work files (6.5). No state file means coverage was not asked for."""
    state = _named(report_files, _COVERAGE_STATE)
    if state is None:
        return None, ()
    if state.read_text(encoding="utf-8").strip() == "missing":
        return None, (_MISSING_PYTEST_COV,)
    cov_json = _named(report_files, _COVERAGE_JSON)
    if cov_json is None:
        return None, ("pytest-cov ran but wrote no coverage report, so coverage is not available",)
    try:
        data = json.loads(cov_json.read_text(encoding="utf-8"))
        files = tuple(
            CoverageFile(path=str(path), line_percent=float(info["summary"]["percent_covered"]))
            for path, info in data["files"].items()
        )
        line_percent = float(data["totals"]["percent_covered"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return None, (f"coverage report could not be read ({type(exc).__name__}), so coverage is not available",)
    return Coverage(line_percent=line_percent, files=files), ()


def _named(report_files: Sequence[Path], name: str) -> Path | None:
    return next((p for p in report_files if p.name == name and p.is_file()), None)


def _timeout(*, exit_code: int | None, warnings: tuple[str, ...] = ()) -> TestResult:
    """A killed run with no report: counts are unavailable (6.3, D9)."""
    return TestResult(
        framework="pytest",
        status=Status.TIMEOUT,
        error=None,
        total=None,
        passed=None,
        failed=None,
        skipped=None,
        errors=None,
        duration_ms=0,
        failures=(),
        flaky=(),
        coverage=None,
        warnings=warnings,
        degraded=False,
        raw=RawInfo(exit_code=exit_code, stdout_path=None, report_path=None),
        command="pytest",
    )


def _error(
    code: ErrorCode,
    message: str,
    *,
    stdout_hint: bool,
    exit_code: int | None,
    warnings: tuple[str, ...] = (),
) -> TestResult:
    hint = "run the command by hand and read the output" if stdout_hint else "fix the import or syntax error first"
    return TestResult(
        framework="pytest",
        status=Status.ERROR,
        error=ErrorInfo(code=code, message=message, hint=hint),
        total=None,
        passed=None,
        failed=None,
        skipped=None,
        errors=None,
        duration_ms=0,
        failures=(),
        flaky=(),
        coverage=None,
        warnings=warnings,
        degraded=False,
        raw=RawInfo(exit_code=exit_code, stdout_path=None, report_path=None),
        command="pytest",
    )
