"""T4 (issue #22): `select` with `framework: all` is refused (requirements 4.3, 6.4, criterion 18).

A path cannot be routed to one framework when several run, so the combined run returns
`error: unsupported_selector` with the reason, and the CLI exits 3.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from test_adapters import api
from test_adapters.model import ErrorCode, Status, TestRequest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "pytest_mixed"


def test_run_all_with_select_is_unsupported_selector() -> None:
    request = TestRequest(cwd=FIXTURE, framework="all", select=("tests/test_mixed.py",))

    combined = api.run_all(request)

    assert combined.status is Status.ERROR
    assert [r.framework for r in combined.results] == ["pytest"]  # one entry per detected framework
    result = combined.results[0]
    assert result.error is not None
    assert result.error.code is ErrorCode.UNSUPPORTED_SELECTOR
    assert "framework all" in result.error.message  # the reason names the cause
    assert result.error.hint  # the result tells the caller what to do
    assert result.total is None  # no run happened, so there are no counts


def test_run_all_without_select_still_runs() -> None:
    combined = api.run_all(TestRequest(cwd=FIXTURE, framework="all"))

    assert combined.results[0].error is None


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", "test_adapters.cli", *args],
        cwd=FIXTURE,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_cli_framework_all_with_select_exits_3(tmp_path: Path) -> None:
    out = tmp_path / "result.json"

    proc = _cli("run", "--framework", "all", "--select", "x", "--result-file", str(out))

    assert proc.returncode == 3, proc.stdout + proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["status"] == "error"
    assert data["results"][0]["error"]["code"] == "unsupported_selector"
