"""Executable form of the Phase 0 done condition for v0.1.0 (docs/architecture/vision.md).

Prints one line per item: `pass` when this repo proves it now, `open` when it needs evidence
this repo does not hold yet (CI links, corpus, matrix, adoption, A/B). Exits 0 only when every
item passes. A rerun after the evidence exists must be able to flip an item to pass, so an
item is never marked pass by default.

Run: `python3 scripts/done_condition.py` from the repo root. Runs no test. Uses the standard
library only, so it works on Windows and Linux and macOS (issue #11 covers Windows testing).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Item:
    number: int
    title: str
    status: str  # "pass" or "open"
    reason: str


def _readme_windows_wording() -> Item:
    """Item 6: the README must say 'implemented, not tested on Windows' and must not claim support or verification."""
    readme = ROOT / "README.md"
    if not readme.is_file():
        return Item(6, "Windows wording", "open", "README.md does not exist")
    text = readme.read_text(encoding="utf-8")
    if not re.search(r"implemented, not tested on Windows", text, re.IGNORECASE):
        return Item(6, "Windows wording", "open", "README lacks the required phrase")
    # A positive claim only: "Windows ... verified" or "Windows ... supported" without a negation before it.
    claim = re.search(r"Windows(?![^.\n]*\bnot\b)[^.\n]*\b(verified|supported)\b", text, re.IGNORECASE)
    if claim:
        return Item(6, "Windows wording", "open", f"README makes a Windows claim: {claim.group(0)!r}")
    return Item(6, "Windows wording", "pass", "README has the required phrase and no Windows claim")


def items() -> list[Item]:
    return [
        Item(1, "Spec tests in CI on Linux and macOS", "open",
             "criteria 1-18, 24, 25 are not all covered; CI has the skeleton and invariant tests only"),
        Item(2, "Agreement with framework counts on the pinned corpus", "open",
             "corpus not cloned in CI (stop condition, vision.md); no agreement report yet"),
        Item(3, "Mutation and platform matrix (criteria 20, 21)", "open",
             "no matrix; pytest 8/9 and jest 29/30 not run; jest not implemented"),
        Item(4, "Adoption: fresh session runs test-adapters on first try (criterion 23)", "open",
             "adoption session needs fresh user approval (stop condition)"),
        Item(5, "A/B pilot recorded (criterion 22)", "open",
             "A/B spend needs fresh user approval; no sessions run"),
        _readme_windows_wording(),
    ]


def main() -> int:
    results = items()
    for item in results:
        print(f"item {item.number}: {item.status:<4}  {item.title}  -- {item.reason}")
    open_count = sum(1 for item in results if item.status != "pass")
    print(f"done condition v0.1.0: {len(results) - open_count} of {len(results)} pass, {open_count} open")
    return 0 if open_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
