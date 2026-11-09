"""Command-line interface (requirements 5.3, 5.4, 5.5). Sketch only.

Exit codes come only from `combine.exit_code_for` and the usage path, so no other module
can invent one (ADR 0002).
"""

from __future__ import annotations

from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the `test-adapters` command. Returns the process exit code."""
    raise NotImplementedError
