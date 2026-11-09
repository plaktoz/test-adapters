"""Adapter registry (requirements 5.2). Adapters register here; nothing else enumerates them.

The first release registers pytest and jest directly. A later release can read entry
points so a third-party adapter needs no edit to this package.
"""

from __future__ import annotations

from test_adapters.adapters.base import Adapter
from test_adapters.errors import UsageError
from test_adapters.model import FrameworkName

# Insertion order is detection order (4.4). Built-in adapters register in `adapters/__init__.py`.
_REGISTRY: dict[str, Adapter] = {}


def register(adapter: Adapter) -> None:
    """Add an adapter. Raises UsageError if the name is already registered."""
    if adapter.name in _REGISTRY:
        raise UsageError(f"adapter {adapter.name!r} is already registered")
    _REGISTRY[adapter.name] = adapter


def get(name: FrameworkName) -> Adapter:
    """Return the adapter for `name`. Raises UsageError for an unknown name."""
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(_REGISTRY) or "none"
        raise UsageError(f"unknown framework {name!r}; registered: {known}") from None


def all_adapters() -> tuple[Adapter, ...]:
    """Every registered adapter, in detection order (4.4: results keep this order)."""
    return tuple(_REGISTRY.values())
