"""Python API (requirements 5.1). Thin wrappers over the internal modules.

These are the names re-exported from `test_adapters/__init__.py`. Nothing else is public.
"""

from __future__ import annotations

from pathlib import Path

from test_adapters import adapters as _builtin_adapters  # noqa: F401  (registers pytest and jest)
from test_adapters.model import (
    AdapterInfo,
    CombinedResult,
    Framework,
    FrameworkName,
    Report,
    TestRequest,
    TestResult,
)


def detect(cwd: Path) -> list[Framework]:
    """Ordered candidates from project files (6.1). Runs nothing."""
    raise NotImplementedError


def run(request: TestRequest) -> TestResult:
    """Build, execute and parse one framework. framework='all' is a UsageError here; use run_all."""
    raise NotImplementedError


def run_all(request: TestRequest) -> CombinedResult:
    """Run every detected framework in turn (4.4)."""
    raise NotImplementedError


def parse(framework: FrameworkName, report_path: Path) -> TestResult:
    """Parse an existing report file without running anything. Must match `run` on the same project (criterion 6).

    Calls the adapter's `parse(report_files=[report_path], exit_code=None, stdout="", timed_out=False)`.
    Raises UsageError for an unknown framework.
    """
    raise NotImplementedError


def parse_text(framework: FrameworkName, stdout: str) -> TestResult:
    """Parse captured stdout when no report file exists. Counts are degraded lower bounds (6.3). Runs nothing.

    Calls the adapter's `parse(report_files=[], exit_code=None, stdout=stdout, timed_out=False)`.
    """
    raise NotImplementedError


def adapter_info(framework: FrameworkName) -> AdapterInfo:
    """Introspection (5.1): how the adapter invokes the tool, its report format and what it needs.

    Raises UsageError for an unknown framework.
    """
    from test_adapters.adapters import registry

    adapter = registry.get(framework)
    return AdapterInfo(
        name=adapter.name,
        command_template=adapter.command_template,
        report_format=adapter.report_format,
        requires=tuple(adapter.requires()),
    )


def doctor(cwd: Path) -> Report:
    """Check that each known framework and its reporter are installed (5.1). Runs no tests (D8)."""
    raise NotImplementedError
