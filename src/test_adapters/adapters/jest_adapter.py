"""jest adapter (requirements 6.1, 6.2, 6.4).

Only `detect` is implemented. `build_command` and `parse` are not, so `run` for jest is not
available yet (Phase 6). Several outcome mappings here are UNVERIFIED (requirements 6.2). They
must be checked live before this adapter is implemented.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from test_adapters.adapters.base import Command
from test_adapters.errors import UsageError
from test_adapters.model import TestRequest, TestResult


class JestAdapter:
    name = "jest"
    command_template = "npx jest --json --outputFile={report} {select}"
    report_format = "jest-json"

    def detect(self, cwd: Path) -> bool:
        """jest.config.*, or package.json with a jest key, or jest in scripts or devDependencies."""
        if any(cwd.glob("jest.config.*")):
            return True
        package = cwd / "package.json"
        if not package.is_file():
            return False
        try:
            data = json.loads(package.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if not isinstance(data, dict):
            return False
        if "jest" in data:
            return True
        scripts = data.get("scripts")
        if isinstance(scripts, dict) and any("jest" in str(value) for value in scripts.values()):
            return True
        dev = data.get("devDependencies")
        return isinstance(dev, dict) and "jest" in dev

    def build_command(self, request: TestRequest, workdir: Path) -> Command:
        """`--json --outputFile=<file>`. Name selectors go through `-t` with a regex-escaped fullName (6.4)."""
        raise UsageError("jest runs are not implemented in this release (Phase 6); use --framework pytest")

    def parse(self, report_files: Sequence[Path], exit_code: int | None, stdout: str, timed_out: bool) -> TestResult:
        """JSON report. Suites that fail to load map to ERROR/collection (4.2)."""
        raise UsageError("jest parsing is not implemented in this release (Phase 6)")

    def requires(self) -> Sequence[str]:
        """`npx` on PATH. It resolves the project's local jest, so jest need not be global."""
        return ("npx",)
