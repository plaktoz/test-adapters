"""Typed errors raised inside the library (requirements 8).

The library never raises for a failing test; that is a TestResult. These exceptions are for
conditions that stop an operation before it can produce a result, such as bad usage.
A consumer may map `ErrorCode` values to its own vocabulary.
"""

from __future__ import annotations

from test_adapters.model import ErrorCode


class TestAdaptersError(Exception):
    """Base class for all library errors."""


class UsageError(TestAdaptersError):
    """Invalid arguments, such as `parallelism` with `framework="all"` on `run()` (5.1). Maps to exit 2."""


class AdapterError(TestAdaptersError):
    """A failure that becomes a TestResult with status ERROR. Carries the error code."""

    def __init__(self, code: ErrorCode, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
