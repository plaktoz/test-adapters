"""Order-dependent (criterion 15): test_b fails when test_a ran earlier in the same process.

Each test appends its name to runs.log in env FIXTURE_STATE_DIR, so a test can show which tests ran.
"""

import os
from pathlib import Path

_ran: list[str] = []


def _log(name: str) -> None:
    with (Path(os.environ["FIXTURE_STATE_DIR"]) / "runs.log").open("a", encoding="utf-8") as log:
        log.write(name + "\n")


def test_a_records():
    _log("a")
    _ran.append("a")


def test_b_fails_after_a():
    _log("b")
    assert "a" not in _ran, "test_a ran earlier in this process"
