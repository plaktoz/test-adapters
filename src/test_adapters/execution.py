"""Child-process execution with timeout and process-tree kill (requirements 6.3).

POSIX only in v0.1.0: Windows is unsupported (D20), so this module uses process groups.
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
    """Run in its own process group. On timeout: SIGTERM the group, wait grace, SIGKILL.

    Child processes of the test are killed too (criterion 3). Output is captured to a file.
    """
    raise NotImplementedError
