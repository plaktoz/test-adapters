"""Fails on every attempt. Each run appends one line to runs.log in env FIXTURE_STATE_DIR, so a test can count runs."""

import os
from pathlib import Path


def test_always_fails():
    with (Path(os.environ["FIXTURE_STATE_DIR"]) / "runs.log").open("a", encoding="utf-8") as log:
        log.write("always_fails\n")
    assert False, "fails on every attempt"
