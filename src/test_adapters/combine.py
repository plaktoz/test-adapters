"""Combining results from several frameworks (requirements 4.4, D12)."""

from __future__ import annotations

from test_adapters.model import STATUS_RANK, CombinedResult, Status, TestResult

__all__ = ["STATUS_RANK", "combine", "exit_code_for"]


def combine(results: tuple[TestResult, ...]) -> CombinedResult:
    """Wrap results in order. The overall status is derived by `CombinedResult.status`. Counts are not summed (4.4)."""
    return CombinedResult(results=results)


_EXIT_CODES: dict[Status, int] = {
    Status.PASSED: 0,
    Status.FAILED: 1,
    Status.ERROR: 3,
    Status.TIMEOUT: 4,
}


def exit_code_for(status: Status) -> int:
    """Map a status to the public exit code (5.4, ADR 0002). Usage errors (2) are not a status."""
    return _EXIT_CODES[status]
