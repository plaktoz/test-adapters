"""Data model: requests, results and their enums (requirements section 4).

Pure data. No I/O, no framework knowledge. Every field name here is the wire name
used in `--json` output, so changing one is a schema_version bump.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal


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


# Worst-first order for the overall status of a CombinedResult (4.4). error outranks failed: a
# framework with no trustworthy result means the repo is not known to be green.
STATUS_RANK: tuple[Status, ...] = (Status.ERROR, Status.TIMEOUT, Status.FAILED, Status.PASSED)

# The set of frameworks is open: an adapter registers under a name (5.2), so a name is a string.
# Whether a name is known is checked by the registry, not by the type.
FrameworkName = str


class FrozenMap(Mapping[str, str]):
    """Read-only, hashable string mapping, so frozen dataclasses stay immutable all the way down."""

    __slots__ = ("_data",)

    def __init__(self, data: Mapping[str, str] | None = None) -> None:
        self._data: dict[str, str] = dict(data) if data else {}

    def __getitem__(self, key: str) -> str:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __hash__(self) -> int:
        return hash(frozenset(self._data.items()))

    def __repr__(self) -> str:
        return f"FrozenMap({self._data!r})"


def freeze(data: Mapping[str, str]) -> FrozenMap:
    """Return `data` as a FrozenMap, copying unless it already is one."""
    return data if isinstance(data, FrozenMap) else FrozenMap(data)


@dataclass(frozen=True)
class Framework:
    """A candidate framework found by detection (6.1)."""

    name: FrameworkName
    evidence: tuple[str, ...]  # project files that matched, for the ambiguity message


@dataclass(frozen=True)
class AdapterInfo:
    """What `adapter_info(framework)` returns (5.1): how an adapter runs and reads a framework."""

    name: FrameworkName
    command_template: str
    report_format: str
    requires: tuple[str, ...]


@dataclass(frozen=True)
class TestRequest:
    """Input to run(). Field names follow requirements section 4.1."""

    __test__ = False  # not a pytest test class, despite the name

    cwd: Path
    framework: FrameworkName | None = None  # None means auto-detect; "all" runs every detected one
    command_override: str | None = None
    select: tuple[str, ...] = ()
    timeout_seconds: int = 600
    parallelism: int | Literal["auto"] | None = "auto"
    coverage: bool = False
    env: Mapping[str, str] = field(default_factory=FrozenMap)
    retry_failed: int = 0
    retry_mode: RetryMode = RetryMode.FILE
    require_tests: bool = True
    kill_grace_seconds: int = 5  # SIGTERM to SIGKILL wait on timeout (6.3)
    max_output_bytes: int = 5 * 1024 * 1024  # tail cap on captured stdout (6.3)

    def __post_init__(self) -> None:
        object.__setattr__(self, "env", freeze(self.env))


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
class CoverageFile:
    """Line coverage of one file (6.5)."""

    path: str
    line_percent: float


@dataclass(frozen=True)
class Coverage:
    """Optional coverage figures (6.5)."""

    line_percent: float
    files: tuple[CoverageFile, ...] = ()


def wire_coverage(coverage: Coverage) -> dict[str, Any]:
    """Coverage as the JSON object in 4.2: `files` is a list of `{path, line_percent}` objects."""
    return {
        "line_percent": coverage.line_percent,
        "files": [{"path": f.path, "line_percent": f.line_percent} for f in coverage.files],
    }


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
    Otherwise total == passed + failed + skipped + errors. The constructor rejects a result
    that breaks the rules in 4.2, so an adapter cannot return one.

    `framework` is None only for an `ambiguous` error, where no single framework was chosen (4.3).
    """

    __test__ = False  # not a pytest test class, despite the name

    framework: FrameworkName | None
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

    def __post_init__(self) -> None:
        if self.status is Status.ERROR:
            if self.error is None:
                raise ValueError("status error requires error info (4.2)")
        elif self.error is not None:
            raise ValueError("error info is allowed only when status is error (4.2)")
        if self.framework is None and not (self.error is not None and self.error.code is ErrorCode.AMBIGUOUS):
            raise ValueError("framework may be None only for an ambiguous error (4.3)")
        counts = (self.total, self.passed, self.failed, self.skipped, self.errors)
        if any(c is None for c in counts):
            if any(c is not None for c in counts):
                raise ValueError("counts must be all set or all None (4.2)")
            if self.status not in (Status.ERROR, Status.TIMEOUT):
                raise ValueError("counts may be None only for error and timeout (4.2)")
            return
        total, passed, failed, skipped, errors = (int(c) for c in counts if c is not None)
        if min(total, passed, failed, skipped, errors) < 0:
            raise ValueError("counts must not be negative")
        if total != passed + failed + skipped + errors:
            raise ValueError("total must equal passed + failed + skipped + errors (4.2)")
        if self.status is Status.PASSED and (failed or errors):
            raise ValueError("status passed requires failed == 0 and errors == 0 (4.2)")
        if self.status is Status.FAILED and not (failed or errors):
            raise ValueError("status failed requires failed + errors > 0 (4.2)")


@dataclass(frozen=True)
class CombinedResult:
    """Outcome of running several frameworks in turn (4.4).

    `status` is derived from `results`, never stored, so it cannot disagree with them. The wire
    form (`json_view`) still writes it as a field.
    """

    results: tuple[TestResult, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not self.results:
            raise ValueError("a combined result needs at least one entry (4.4)")

    @property
    def status(self) -> Status:
        """The worst entry, in the order error > timeout > failed > passed (4.4)."""
        return min((r.status for r in self.results), key=STATUS_RANK.index)


@dataclass(frozen=True)
class FrameworkStatus:
    """Availability of one framework and its reporter, as reported by doctor (5.1)."""

    name: FrameworkName
    detected: bool
    available: bool  # framework binary and reporter both present
    hint: str  # install hint when not available, else ""


@dataclass(frozen=True)
class Report:
    """Output of doctor(). One entry per known framework, whether or not it was detected."""

    frameworks: tuple[FrameworkStatus, ...]
    schema_version: int = 1
