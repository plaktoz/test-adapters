"""test-adapters: run pytest or jest and return one normalised result.

Public surface (see docs/requirements.md section 5.1). Everything else is internal.
"""

from test_adapters.api import detect, doctor, parse, parse_text, run, run_all
from test_adapters.model import (
    CombinedResult,
    Coverage,
    ErrorCode,
    ErrorInfo,
    Failure,
    FlakyTest,
    Framework,
    FrameworkStatus,
    Report,
    RetryMode,
    Status,
    TestRequest,
    TestResult,
)
from test_adapters.errors import TestAdaptersError

__all__ = [
    "CombinedResult",
    "Coverage",
    "ErrorCode",
    "ErrorInfo",
    "Failure",
    "FlakyTest",
    "Framework",
    "FrameworkStatus",
    "Report",
    "RetryMode",
    "Status",
    "TestAdaptersError",
    "TestRequest",
    "TestResult",
    "detect",
    "doctor",
    "parse",
    "parse_text",
    "run",
    "run_all",
]
