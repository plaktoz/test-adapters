"""One test fails once and then passes (flaky). Another passes once and then fails on a retry (warning only).

Markers in env FIXTURE_STATE_DIR record which attempt this is.
"""

import os
from pathlib import Path


def _first_attempt(name: str) -> bool:
    marker = Path(os.environ["FIXTURE_STATE_DIR"]) / (name + ".marker")
    if marker.exists():
        return False
    marker.write_text("seen\n", encoding="utf-8")
    return True


def test_fails_once():
    if _first_attempt("fails_once"):
        assert False, "fails on the first attempt"


def test_passes_then_fails():
    if _first_attempt("passes_then_fails"):
        return
    assert False, "passes on the first attempt, fails on the retry"
