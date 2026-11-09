"""Framework detection (requirements 6.1). Reads files only; runs nothing (D8)."""

from __future__ import annotations

from pathlib import Path

from test_adapters.model import Framework


def detect(cwd: Path) -> list[Framework]:
    """Every adapter whose `detect` matches, in registry order. Empty list if none."""
    raise NotImplementedError
