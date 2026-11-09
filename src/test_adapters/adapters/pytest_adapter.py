"""pytest adapter (requirements 6.1, 6.2, 6.4). Sketch only: bodies are not implemented."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from test_adapters.adapters.base import Command
from test_adapters.model import TestRequest, TestResult


class PytestAdapter:
    name = "pytest"

    def detect(self, cwd: Path) -> bool:
        """pytest.ini, pyproject [tool.pytest*], tox.ini/setup.cfg pytest section, conftest.py, or tests/test_*.py."""
        raise NotImplementedError

    def build_command(self, request: TestRequest, workdir: Path) -> Command:
        """`--junitxml=<file>`; selectors are node IDs or file paths passed as arguments."""
        raise NotImplementedError

    def parse(self, command: Command, exit_code: int | None, stdout: str, timed_out: bool) -> TestResult:
        """JUnit XML first. file and line come from the traceback's `path:line: ErrorType` line (6.2)."""
        raise NotImplementedError

    def requires(self) -> Sequence[str]:
        return ("pytest",)
