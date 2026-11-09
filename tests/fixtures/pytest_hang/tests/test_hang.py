"""Fixture for T6: spawn a child process, record its PID, then hang past the timeout."""

import os
import subprocess
import sys
import time
from pathlib import Path


def test_hangs_with_a_child():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    Path(os.environ["TA_CHILD_PID_FILE"]).write_text(str(child.pid), encoding="utf-8")
    time.sleep(600)
