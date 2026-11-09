"""Adapter registry (requirements 5.2). Adapters register here; nothing else enumerates them.

The first release registers pytest and jest directly. A later release can read entry
points so a third-party adapter needs no edit to this package.
"""

from __future__ import annotations

from test_adapters.adapters.base import Adapter
from test_adapters.model import FrameworkName

_REGISTRY: dict[str, Adapter] = {}


def register(adapter: Adapter) -> None:
    """Add an adapter. Raises UsageError if the name is already registered."""
    raise NotImplementedError


def get(name: FrameworkName) -> Adapter:
    """Return the adapter for `name`. Raises UsageError for an unknown name."""
    raise NotImplementedError


def all_adapters() -> tuple[Adapter, ...]:
    """Every registered adapter, in detection order (4.4: results keep this order)."""
    raise NotImplementedError
