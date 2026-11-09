"""Built-in adapters. Importing this package registers them, in detection order (4.4)."""

from __future__ import annotations

from test_adapters.adapters import registry
from test_adapters.adapters.jest_adapter import JestAdapter
from test_adapters.adapters.pytest_adapter import PytestAdapter

if "pytest" not in {a.name for a in registry.all_adapters()}:
    registry.register(PytestAdapter())
if "jest" not in {a.name for a in registry.all_adapters()}:
    registry.register(JestAdapter())
