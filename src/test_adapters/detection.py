"""Framework detection (requirements 6.1). Reads files only; runs nothing (D8)."""

from __future__ import annotations

from pathlib import Path

from test_adapters.adapters import registry
from test_adapters.model import Framework


def detect(cwd: Path) -> list[Framework]:
    """Every adapter whose `detect` matches, in registry order. Empty list if none.

    `evidence` is empty: the adapter reports a yes or no, not the file that matched.
    """
    return [Framework(name=adapter.name, evidence=()) for adapter in registry.all_adapters() if adapter.detect(cwd)]
