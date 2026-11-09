"""Windows kill path (requirements 6.3, D20).

These tests run on Linux and macOS. They mock `subprocess` and check the command that is
built. They do not run anything on Windows, so a passing run does not show that Windows
behaves this way. The Windows path is verified by reading only.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from test_adapters.adapters.base import Command
from test_adapters.execution import kill_tree_windows, run_process

# Windows-only constant. subprocess defines it on win32 only, so the tests supply it.
CREATE_NEW_PROCESS_GROUP = 0x00000200


class FakeProc:
    """Stands in for subprocess.Popen. `wait(timeout=...)` raises when the process hangs."""

    def __init__(self, pid: int, hang: bool) -> None:
        self.pid = pid
        self.hang = hang
        self.returncode: int | None = None

    def wait(self, timeout: float | None = None) -> int:
        if timeout is not None and self.hang:
            raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout)
        self.returncode = 1
        return 1


class Recorder:
    def __init__(self) -> None:
        self.popen_calls: list[dict[str, object]] = []
        self.run_calls: list[tuple[list[str], dict[str, object]]] = []


def _install_fakes(monkeypatch: pytest.MonkeyPatch, pid: int, hang: bool, run_returncode: int = 0) -> Recorder:
    rec = Recorder()

    def fake_popen(argv: list[str], **kwargs: object) -> FakeProc:
        rec.popen_calls.append({"argv": argv, **kwargs})
        return FakeProc(pid, hang)

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        rec.run_calls.append((list(argv), dict(kwargs)))
        return subprocess.CompletedProcess(argv, run_returncode, "", "")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(subprocess, "run", fake_run)
    return rec


def _command() -> Command:
    return Command(argv=("pytest", "-q"), env={}, report_paths=())


class TestKillTreeWindows:
    def test_runs_taskkill_tree_force_on_pid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rec = _install_fakes(monkeypatch, pid=4321, hang=False)

        kill_tree_windows(4321)

        assert len(rec.run_calls) == 1
        argv, kwargs = rec.run_calls[0]
        assert argv == ["taskkill", "/T", "/F", "/PID", "4321"]
        assert kwargs.get("check", False) is False

    def test_missing_process_does_not_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A non-zero exit from taskkill, here 128, means the process may already be gone. The
        # code ignores it. The value 128 is not verified on Windows; only the ignore rule is tested.
        rec = _install_fakes(monkeypatch, pid=4321, hang=False, run_returncode=128)

        kill_tree_windows(4321)

        assert len(rec.run_calls) == 1


class TestRunProcessWindowsSpawn:
    def test_child_starts_in_new_process_group(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(subprocess, "CREATE_NEW_PROCESS_GROUP", CREATE_NEW_PROCESS_GROUP, raising=False)
        rec = _install_fakes(monkeypatch, pid=4321, hang=False)

        outcome = run_process(_command(), tmp_path, timeout_seconds=5, kill_grace_seconds=1, max_output_bytes=1024)
        outcome.stdout_path.unlink()

        assert len(rec.popen_calls) == 1
        kwargs = rec.popen_calls[0]
        assert kwargs["creationflags"] == CREATE_NEW_PROCESS_GROUP
        assert not kwargs.get("start_new_session", False)
        assert outcome.timed_out is False

    def test_timeout_runs_taskkill_on_child_pid(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(subprocess, "CREATE_NEW_PROCESS_GROUP", CREATE_NEW_PROCESS_GROUP, raising=False)
        rec = _install_fakes(monkeypatch, pid=4321, hang=True)

        outcome = run_process(_command(), tmp_path, timeout_seconds=5, kill_grace_seconds=1, max_output_bytes=1024)
        outcome.stdout_path.unlink()

        assert outcome.timed_out is True
        assert outcome.exit_code is None
        assert [argv for argv, _ in rec.run_calls] == [["taskkill", "/T", "/F", "/PID", "4321"]]


class TestRunProcessPosixSpawn:
    def test_child_starts_in_new_session_without_creation_flags(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        rec = _install_fakes(monkeypatch, pid=4321, hang=False)

        outcome = run_process(_command(), tmp_path, timeout_seconds=5, kill_grace_seconds=1, max_output_bytes=1024)
        outcome.stdout_path.unlink()

        kwargs = rec.popen_calls[0]
        assert kwargs["start_new_session"] is True
        assert "creationflags" not in kwargs
        assert rec.run_calls == []
