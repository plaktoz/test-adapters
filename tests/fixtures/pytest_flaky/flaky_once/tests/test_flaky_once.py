"""Fails on the first attempt and passes on every later one.

The state directory (env FIXTURE_STATE_DIR) holds a marker that says the first attempt happened.
"""

import os
from pathlib import Path


def test_flaky_once():
    marker = Path(os.environ["FIXTURE_STATE_DIR"]) / "flaky_once.marker"
    if not marker.exists():
        marker.write_text("first attempt\n", encoding="utf-8")
        assert False, "fails on the first attempt"
