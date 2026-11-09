"""T6 (issue #24): a timeout kills the test's child processes too (POSIX).

Criterion 3 and the mutation table row 3 (requirements 9, 9.1). The fixture test spawns a
child and sleeps far past the limit. The run must exit 4, report `timeout` with null counts,
and leave the child dead. The Windows tree kill is covered by tests/test_windows_kill.py.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "pytest_hang"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX process group only; Windows is covered by test_windows_kill.py")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def test_timeout_exits_4_with_null_counts_and_no_child_left(tmp_path: Path):
    pid_file = tmp_path / "child.pid"
    result_file = tmp_path / "result.json"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "TA_CHILD_PID_FILE": str(pid_file)}
    proc = subprocess.run(
        [sys.executable, "-m", "test_adapters.cli", "run", "--timeout", "2", "--result-file", str(result_file)],
        cwd=FIXTURE,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 4, proc.stdout + proc.stderr
    data = json.loads(result_file.read_text(encoding="utf-8"))
    assert data["status"] == "timeout"
    assert data["total"] is None  # never an invented 0 (D9)
    assert pid_file.is_file(), "the fixture did not record its child PID"
    child_pid = int(pid_file.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 5
    while _alive(child_pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    alive = _alive(child_pid)
    if alive:
        os.kill(child_pid, 9)  # clean up before failing, so the test never leaks a process
    assert not alive, f"child process {child_pid} survived the timeout"
