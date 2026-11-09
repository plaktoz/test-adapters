"""Output views (requirements 5.5). Pure functions from result to text or JSON.

The default text view is for agents. Its fields and rules are contract; its layout is not.
"""

from __future__ import annotations

from test_adapters.model import CombinedResult, TestResult


def text_view(
    result: TestResult,
    full: bool = False,
    fields: tuple[str, ...] = (),
    max_failures: int = 20,
    message_limit: int = 200,
) -> str:
    """Default view for one framework (5.5). `full` lifts the message cut. `fields` adds failure fields."""
    raise NotImplementedError


def combined_text_view(result: CombinedResult, full: bool = False, fields: tuple[str, ...] = ()) -> str:
    """One overall status line, then one block per framework (5.5)."""
    raise NotImplementedError


def json_view(result: TestResult | CombinedResult) -> str:
    """Complete JSON. Never truncated (criterion 8).

    A CombinedResult writes its derived `status` as a field. Coverage files go through
    `model.wire_coverage`.
    """
    raise NotImplementedError
