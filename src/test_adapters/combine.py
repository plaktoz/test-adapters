"""Combining results from several frameworks (requirements 4.4, D12)."""

from __future__ import annotations

from test_adapters.model import CombinedResult, Status, TestResult

# Worst-first order for the overall status (4.4). error outranks failed: a framework with no
# trustworthy result means the repo is not known to be green.
STATUS_RANK: tuple[Status, ...] = (Status.ERROR, Status.TIMEOUT, Status.FAILED, Status.PASSED)


def combine(results: tuple[TestResult, ...]) -> CombinedResult:
    """Overall status is the worst entry. Counts are not summed (4.4)."""
    raise NotImplementedError


def exit_code_for(status: Status) -> int:
    """Map a status to the public exit code (5.4, ADR 0002)."""
    raise NotImplementedError
