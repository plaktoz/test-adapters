"""Adapter interface (requirements 5.2). Adding a framework means adding one module here.

Adapters register through the registry in `registry.py`. Existing code never changes
when a new adapter is added (criterion 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from test_adapters.model import TestRequest, TestResult


@dataclass(frozen=True)
class Command:
    """What to execute. Built by an adapter, run by `execution.run_process`."""

    argv: tuple[str, ...]
    env: dict[str, str]
    report_paths: tuple[Path, ...]  # machine-readable outputs to read after the run
    stdout_progress_flags: tuple[str, ...] = ()  # extra flags needed for stdout counts after a timeout (6.3)


class Adapter(Protocol):
    """One framework. Implementations are stateless; all state lives in the request and result."""

    name: str  # "pytest" | "jest"

    def detect(self, cwd: Path) -> bool:
        """True when the project files for this framework are present (6.1)."""
        ...

    def build_command(self, request: TestRequest, workdir: Path) -> Command:
        """Build argv for a run, including selectors and report flags (6.2, 6.4).

        Raises AdapterError(UNSUPPORTED_SELECTOR) when `select` cannot be expressed.
        """
        ...

    def parse(
        self,
        command: Command,
        exit_code: int | None,
        stdout: str,
        timed_out: bool,
    ) -> TestResult:
        """Build a TestResult from report files, falling back to stdout (6.2, 6.3).

        Must return status ERROR with the correct code for collection, no_tests and
        unparseable_report. Never raises for a failing test.
        """
        ...

    def requires(self) -> Sequence[str]:
        """Binaries and plugins needed, for `doctor` and `tool_missing` hints."""
        ...
