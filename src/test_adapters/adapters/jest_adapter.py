"""jest adapter (requirements 6.1, 6.2, 6.4). Sketch only: bodies are not implemented.

Several outcome mappings here are UNVERIFIED (requirements 6.2). They must be checked
live before this adapter is implemented.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from test_adapters.adapters.base import Command
from test_adapters.model import TestRequest, TestResult


class JestAdapter:
    name = "jest"
    command_template = "npx jest --json --outputFile={report} {select}"
    report_format = "jest-json"

    def detect(self, cwd: Path) -> bool:
        """jest.config.*, or package.json with a jest key or jest in scripts/devDependencies."""
        raise NotImplementedError

    def build_command(self, request: TestRequest, workdir: Path) -> Command:
        """`--json --outputFile=<file>`. Name selectors go through `-t` with a regex-escaped fullName (6.4)."""
        raise NotImplementedError

    def parse(self, report_files: Sequence[Path], exit_code: int | None, stdout: str, timed_out: bool) -> TestResult:
        """JSON report. Suites that fail to load map to ERROR/collection (4.2)."""
        raise NotImplementedError

    def requires(self) -> Sequence[str]:
        return ("npx", "jest")
