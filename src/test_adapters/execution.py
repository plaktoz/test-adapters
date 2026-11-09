"""Child-process execution with timeout and process-tree kill (requirements 6.3).

Two implementations behind one function. POSIX uses a process group and SIGTERM/SIGKILL.
Windows starts the child in a new process group and kills the tree with `taskkill /T /F`.
The Windows path is implemented but has no CI job in v0.1.0 (D20). Its tests in
`tests/test_windows_kill.py` mock `subprocess` and run on Linux and macOS. They check the
command built, not the behaviour on Windows.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from test_adapters.adapters.base import Command


@dataclass(frozen=True)
class ProcessOutcome:
    exit_code: int | None  # None when killed by timeout
    timed_out: bool
    stdout_path: Path  # tail-capped at max_output_bytes
    duration_ms: int


def run_process(
    command: Command,
    cwd: Path,
    timeout_seconds: int,
    kill_grace_seconds: int,
    max_output_bytes: int,
) -> ProcessOutcome:
    """Run in its own process group or tree. On timeout, kill the whole tree (criterion 3).

    POSIX: start with `start_new_session=True`. On timeout, send SIGTERM to the group,
    wait `kill_grace_seconds`, then SIGKILL.
    Windows: start with `creationflags=CREATE_NEW_PROCESS_GROUP`. On timeout, run
    `taskkill /T /F /PID <pid>`, which kills the child tree. `kill_grace_seconds` is not used
    there, because taskkill /F has no graceful step.

    Output goes to a file, tail-capped at `max_output_bytes`.
    """
    import os
    import subprocess
    import sys
    import tempfile
    import time

    out_fd, out_name = tempfile.mkstemp(prefix="test-adapters-", suffix=".log")
    started = time.monotonic()
    with os.fdopen(out_fd, "wb") as out:
        if sys.platform == "win32":
            proc = subprocess.Popen(
                list(command.argv),
                cwd=cwd,
                env={**os.environ, **command.env},
                stdout=out,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            proc = subprocess.Popen(
                list(command.argv),
                cwd=cwd,
                env={**os.environ, **command.env},
                stdout=out,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        timed_out = False
        try:
            exit_code: int | None = proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            if sys.platform == "win32":
                kill_tree_windows(proc.pid)
            else:
                kill_group_posix(proc.pid, kill_grace_seconds)
            proc.wait()
            exit_code = None

    _tail_cap(Path(out_name), max_output_bytes)
    duration_ms = int((time.monotonic() - started) * 1000)
    return ProcessOutcome(
        exit_code=exit_code,
        timed_out=timed_out,
        stdout_path=Path(out_name),
        duration_ms=duration_ms,
    )


def _tail_cap(path: Path, limit: int) -> None:
    """Keep only the last `limit` bytes of `path` (6.3)."""
    size = path.stat().st_size
    if size <= limit:
        return
    with path.open("rb+") as f:
        f.seek(size - limit)
        tail = f.read()
        f.seek(0)
        f.write(tail)
        f.truncate()


def kill_tree_windows(pid: int) -> None:
    """Kill a process and every descendant with `taskkill /T /F /PID <pid>` (6.3).

    The return code is ignored on purpose. taskkill fails when the PID is already gone,
    and the caller only needs the tree to be dead.
    """
    import subprocess

    subprocess.run(
        ["taskkill", "/T", "/F", "/PID", str(pid)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def kill_group_posix(pgid: int, grace_seconds: int) -> None:
    """SIGTERM the process group, wait `grace_seconds`, then SIGKILL it (6.3)."""
    import os
    import signal
    import time

    # EPERM on a group that still exists means "alive, but not ours to signal", so treat it as alive.
    try:
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return
        except PermissionError:
            pass
        time.sleep(0.05)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
