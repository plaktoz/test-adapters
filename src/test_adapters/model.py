"""Data model: requests, results and their enums (requirements section 4).

Pure data. No I/O, no framework knowledge. Every field name here is the wire name
used in `--json` output, so changing one is a schema_version bump.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal


class Status(str, Enum):
    """Verdict of a TestResult (4.2). Overall status of a CombinedResult uses the same values."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"


class ErrorCode(str, Enum):
    """Typed reason for status ERROR (4.3)."""

    TOOL_MISSING = "tool_missing"
    COLLECTION = "collection"
    NO_TESTS = "no_tests"
    UNPARSEABLE_REPORT = "unparseable_report"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED_SELECTOR = "unsupported_selector"


class RetryMode(str, Enum):
    """What a retry re-runs (6.4). Recorded on each flaky entry."""

    FILE = "file"
    ISOLATED = "isolated"


FrameworkName = Literal["pytest", "jest"]


@dataclass(frozen=True)
class Framework:
    """A candidate framework found by detection (6.1)."""

    name: FrameworkName
    evidence: tuple[str, ...]  # project files that matched, for the ambiguity message


@dataclass(frozen=True)
class TestRequest:
    """Input to run(). Field names follow requirements section 4.1."""

    cwd: Path
    framework: FrameworkName | Literal["all"] | None = None  # None means auto-detect
    command_override: str | None = None
    select: tuple[str, ...] = ()
    timeout_seconds: int = 600
    parallelism: int | Literal["auto"] | None = "auto"
    coverage: bool = False
    env: dict[str, str] = field(default_factory=dict)
    retry_failed: int = 0
    retry_mode: RetryMode = RetryMode.FILE
    require_tests: bool = True


@dataclass(frozen=True)
class Failure:
    """A test still failing after retries (4.2). file and line are None when undeterminable."""

    name: str
    message: str
    file: str | None
    line: int | None


@dataclass(frozen=True)
class FlakyTest:
    """A test that failed at least once and passed on a later attempt (4.2)."""

    name: str
    attempts: int
    retry_mode: RetryMode


@dataclass(frozen=True)
class Coverage:
    """Optional coverage figures (6.5)."""

    line_percent: float
    files: tuple[tuple[str, float], ...] = ()  # (path, line_percent)


@dataclass(frozen=True)
class ErrorInfo:
    """Present only when status is ERROR (4.2 rule)."""

    code: ErrorCode
    message: str
    hint: str


@dataclass(frozen=True)
class RawInfo:
    """Pointers to unparsed output. Kept so a caller can read detail without rerunning."""

    exit_code: int | None
    stdout_path: str | None
    report_path: str | None


@dataclass(frozen=True)
class TestResult:
    """Outcome of one run of one framework (4.2).

    Counts are None (not 0) only for timeout and error with no count source (6.3, D9).
    Otherwise total == passed + failed + skipped + errors.
    """

    framework: FrameworkName
    status: Status
    error: ErrorInfo | None
    total: int | None
    passed: int | None
    failed: int | None
    skipped: int | None
    errors: int | None
    duration_ms: int
    failures: tuple[Failure, ...]
    flaky: tuple[FlakyTest, ...]
    coverage: Coverage | None
    warnings: tuple[str, ...]
    degraded: bool
    raw: RawInfo
    command: str
    schema_version: int = 1


@dataclass(frozen=True)
class CombinedResult:
    """Outcome of running several frameworks in turn (4.4)."""

    status: Status
    results: tuple[TestResult, ...]
    schema_version: int = 1
