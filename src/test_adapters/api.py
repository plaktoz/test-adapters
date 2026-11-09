"""Python API (requirements 5.1). Thin wrappers over the internal modules.

These are the names re-exported from `test_adapters/__init__.py`. Nothing else is public.
"""

from __future__ import annotations

from pathlib import Path

from test_adapters.model import CombinedResult, Framework, TestRequest, TestResult


def detect(cwd: Path) -> list[Framework]:
    """Ordered candidates from project files (6.1). Runs nothing."""
    raise NotImplementedError


def run(request: TestRequest) -> TestResult:
    """Build, execute and parse one framework. framework='all' is a UsageError here; use run_all."""
    raise NotImplementedError


def run_all(request: TestRequest) -> CombinedResult:
    """Run every detected framework in turn (4.4)."""
    raise NotImplementedError


def parse(framework: str, report_path_or_text: str) -> TestResult:
    """Parse an existing report without running anything. Must match `run` on the same project (criterion 6)."""
    raise NotImplementedError


def doctor(cwd: Path) -> dict[str, object]:
    """Check that each detected framework and its reporter are installed (5.1)."""
    raise NotImplementedError
