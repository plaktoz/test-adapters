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
from test_adapters.errors import AdapterError, UsageError
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
from test_adapters.retry import with_retries


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
    missing = _missing(adapter, request.cwd)
    if missing:
        return _error_result(
            name,
            ErrorCode.TOOL_MISSING,
            f"{adapter.name} needs {', '.join(missing)}, which was not found",
            _install_hint(adapter, missing),
        )

    first = _run_once(adapter, request)
    if request.retry_failed <= 0:
        return first
    return with_retries(
        first,
        lambda selection: _run_once(adapter, replace(request, select=selection, retry_failed=0)),
        request.retry_failed,
        request.retry_mode,
    )


def _run_once(adapter: Adapter, request: TestRequest) -> TestResult:
    """One execution of the framework in a fresh workdir, so no attempt reads another's report (6.4)."""
    workdir = Path(tempfile.mkdtemp(prefix="test-adapters-run-"))
    try:
        command = adapter.build_command(request, workdir)
    except AdapterError as exc:
        # An adapter that cannot express the request (4.3, base.py) gives a result, not an exception.
        return _error_result(adapter.name, exc.code, exc.message, exc.hint)
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
    if request.select:
        # A path or node ID cannot be routed to one framework when several run (4.3, 6.4). No run happens.
        return combine(
            tuple(
                _error_result(
                    framework.name,
                    ErrorCode.UNSUPPORTED_SELECTOR,
                    "select cannot be used with framework all, because a path cannot be routed to one framework",
                    "run one framework at a time with --framework <name> and --select",
                )
                for framework in found
            )
        )
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
            available=not missing,
            hint=f"install {', '.join(missing)}" if missing else "",
        )
        for adapter in registry.all_adapters()
        for missing in (_missing(adapter, cwd),)
    )
    return Report(frameworks=statuses)


def _install_hint(adapter: Adapter, missing: list[str]) -> str:
    """How to get `missing`. An adapter whose tool lives in the project says so itself (`install_hint`)."""
    hint = getattr(adapter, "install_hint", None)
    if hint is not None:
        return str(hint)
    return f"install {', '.join(missing)} into the interpreter that runs test-adapters"


def _missing(adapter: Adapter, cwd: Path) -> list[str]:
    """Requirements of `adapter` that are not available (5.1, 6.1).

    A requirement is present when it is on PATH or importable. An adapter whose tool lives in the
    project (jest in `node_modules`) may also define `missing_in(cwd)`, which names what that
    project lacks. `shutil.which("npx")` alone would say jest is available in a project without it.
    """
    missing: list[str] = []
    for name in adapter.requires():
        if shutil.which(name) is None and importlib.util.find_spec(name) is None:
            missing.append(name)
    project_check = getattr(adapter, "missing_in", None)
    if project_check is not None:
        missing.extend(project_check(cwd))
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
