"""T8 (issue #26): pytest collection errors and zero-test reports map to error, exit 3.

Runs the real CLI in a subprocess. Criteria 2, 9 and 12 (requirements section 9).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", "test_adapters.cli", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_collection_error_is_error_not_failed_and_exits_3(tmp_path: Path):
    # Criterion 2: a module that fails to import gives status error, code collection, exit 3.
    out = tmp_path / "result.json"
    proc = cli("run", "--result-file", str(out), cwd=FIXTURES / "pytest_collection")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["status"] == "error"
    assert data["error"]["code"] == "collection"
    assert data["failures"] == []
    assert data["total"] is None  # counts are null when no count source exists (4.2)


def test_collection_error_view_names_the_code_and_help(tmp_path: Path):
    # Criterion 9: status error prints a typed error: line and a help: line.
    proc = cli("run", cwd=FIXTURES / "pytest_collection")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "status: error" in proc.stdout
    assert "error: collection" in proc.stdout
    assert "help:" in proc.stdout


def test_zero_tests_is_error_no_tests_and_exits_3(tmp_path: Path):
    # Criterion 9 and requirements 4.3: zero collected tests is error, code no_tests, exit 3.
    out = tmp_path / "result.json"
    proc = cli("run", "--result-file", str(out), cwd=FIXTURES / "pytest_no_tests")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["status"] == "error"
    assert data["error"]["code"] == "no_tests"


def test_failure_without_traceback_line_has_null_line(tmp_path: Path):
    # Criterion 12: when no path:line match exists, line is null and the file is kept.
    # Covered at the adapter level: _location returns (None, None) for text with no match.
    from test_adapters.adapters.pytest_adapter import _location

    assert _location("assert 1 == 2\nno location here") == (None, None)
