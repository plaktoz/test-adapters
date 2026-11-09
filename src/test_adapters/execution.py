"""Child-process execution with timeout and process-tree kill (requirements 6.3).

Two implementations behind one function. POSIX uses a process group and SIGTERM/SIGKILL.
Windows starts the child in a new process group and kills the tree with `taskkill /T /F`.
The Windows path is implemented but has no CI job in v0.1.0 (D20). Its tests are marked
`windows_untested` and run only when a Windows environment is available.
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
    raise NotImplementedError


def kill_tree_windows(pid: int) -> None:
    """Kill a process and every descendant with `taskkill /T /F /PID <pid>` (6.3)."""
    raise NotImplementedError


def kill_group_posix(pgid: int, grace_seconds: int) -> None:
    """SIGTERM the process group, wait `grace_seconds`, then SIGKILL it (6.3)."""
    raise NotImplementedError
