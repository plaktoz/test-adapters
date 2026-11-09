"""Python API (requirements 5.1). Thin wrappers over the internal modules.

These are the names re-exported from `test_adapters/__init__.py`. Nothing else is public.
"""

from __future__ import annotations

import importlib.util
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path

from test_adapters import adapters as _builtin_adapters  # noqa: F401  (registers pytest and jest)
from test_adapters.adapters import registry
from test_adapters.adapters.base import Adapter
from test_adapters.combine import combine
from test_adapters.detection import detect as _detect
from test_adapters.errors import UsageError
from test_adapters.execution import run_process
from test_adapters.model import (
    AdapterInfo,
    CombinedResult,
    ErrorCode,
    ErrorInfo,
    Framework,
    FrameworkName,
    FrameworkStatus,
    RawInfo,
    Report,
    Status,
    TestRequest,
    TestResult,
)


def detect(cwd: Path) -> list[Framework]:
    """Ordered candidates from project files (6.1). Runs nothing."""
    return _detect(cwd)


def run(request: TestRequest) -> TestResult:
    """Build, execute and parse one framework. framework='all' is a UsageError here; use run_all."""
    if request.framework == "all":
        raise UsageError("framework='all' is not a single run; use run_all")
    if request.framework is None:
        found = _detect(request.cwd)
        if len(found) > 1:
            names = ", ".join(f.name for f in found)
            return _error_result(
                None,
                ErrorCode.AMBIGUOUS,
                f"several frameworks detected: {names}",
                "pass --framework <name>, --framework all, or pin framework in test-adapters.toml",
            )
        if not found:
            raise UsageError("no framework detected in the working directory; pass --framework <name>")
        name = found[0].name
    else:
        name = request.framework

    adapter = registry.get(name)
    missing = _missing(adapter)
    if missing:
        return _error_result(
            name,
            ErrorCode.TOOL_MISSING,
            f"{adapter.name} needs {', '.join(missing)}, which was not found",
            f"install {', '.join(missing)} into the interpreter that runs test-adapters",
        )

    workdir = Path(tempfile.mkdtemp(prefix="test-adapters-run-"))
    command = adapter.build_command(request, workdir)
    outcome = run_process(
        command,
        request.cwd,
        request.timeout_seconds,
        request.kill_grace_seconds,
        request.max_output_bytes,
    )
    stdout = outcome.stdout_path.read_text(encoding="utf-8", errors="replace")
    reports = [p for p in command.report_paths if p.exists()]
    result = adapter.parse(reports, outcome.exit_code, stdout, outcome.timed_out)
    return replace(
        result,
        raw=replace(result.raw, stdout_path=str(outcome.stdout_path)),
        command=" ".join(command.argv),
    )


def run_all(request: TestRequest) -> CombinedResult:
    """Run every detected framework in turn (4.4). One result per framework, in detection order.

    A framework that cannot run becomes its own error entry, and the others still run (4.4).
    """
    found = _detect(request.cwd)
    if not found:
        raise UsageError("no framework detected in the working directory; pass --framework <name>")
    results: list[TestResult] = []
    for framework in found:
        try:
            results.append(run(replace(request, framework=framework.name)))
        except UsageError as exc:
            results.append(_error_result(framework.name, ErrorCode.TOOL_MISSING, str(exc), "run it alone with --framework"))
    return combine(tuple(results))


def parse(framework: FrameworkName, report_path: Path) -> TestResult:
    """Parse an existing report file without running anything. Must match `run` on the same project (criterion 6).

    Calls the adapter's `parse(report_files=[report_path], exit_code=None, stdout="", timed_out=False)`.
    Raises UsageError for an unknown framework.
    """
    return registry.get(framework).parse([report_path], None, "", False)


def parse_text(framework: FrameworkName, stdout: str) -> TestResult:
    """Parse captured stdout when no report file exists. Counts are degraded lower bounds (6.3). Runs nothing.

    Calls the adapter's `parse(report_files=[], exit_code=None, stdout=stdout, timed_out=False)`.
    """
    return registry.get(framework).parse([], None, stdout, False)


def adapter_info(framework: FrameworkName) -> AdapterInfo:
    """Introspection (5.1): how the adapter invokes the tool, its report format and what it needs.

    Raises UsageError for an unknown framework.
    """
    adapter = registry.get(framework)
    return AdapterInfo(
        name=adapter.name,
        command_template=adapter.command_template,
        report_format=adapter.report_format,
        requires=tuple(adapter.requires()),
    )


def doctor(cwd: Path) -> Report:
    """Check that each known framework and its reporter are installed (5.1). Runs no tests (D8).

    A requirement is present when it is an executable on PATH or an importable Python module
    in the running interpreter. Versions and plugins are not checked.
    """
    statuses = tuple(
        FrameworkStatus(
            name=adapter.name,
            detected=adapter.detect(cwd),
            available=not _missing(adapter),
            hint="" if not _missing(adapter) else f"install {', '.join(_missing(adapter))}",
        )
        for adapter in registry.all_adapters()
    )
    return Report(frameworks=statuses)


def _missing(adapter: Adapter) -> list[str]:
    """Requirements of `adapter` that are neither on PATH nor importable (5.1, 6.1)."""
    missing: list[str] = []
    for name in adapter.requires():
        if shutil.which(name) is None and importlib.util.find_spec(name) is None:
            missing.append(name)
    return missing


def _error_result(framework: FrameworkName | None, code: ErrorCode, message: str, hint: str) -> TestResult:
    """A status ERROR result with no counts (4.2, 4.3). `framework` is None only for ambiguous."""
    return TestResult(
        framework=framework,
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
        warnings=(),
        degraded=False,
        raw=RawInfo(exit_code=None, stdout_path=None, report_path=None),
        command="",
    )
