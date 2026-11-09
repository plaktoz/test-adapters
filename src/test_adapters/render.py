"""Output views (requirements 5.5). Pure functions from result to text or JSON.

The default text view is for agents. Its fields and rules are contract; its layout is not.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path

from test_adapters.model import CombinedResult, TestResult, wire_coverage

MESSAGE_LIMIT = 200
FAILURE_LIMIT = 20


def text_view(
    result: TestResult,
    full: bool = False,
    fields: tuple[str, ...] = (),
    max_failures: int = FAILURE_LIMIT,
    message_limit: int = MESSAGE_LIMIT,
) -> str:
    """Default view for one framework (5.5). `full` lifts the message cut. `fields` adds failure fields.

    `fields` is accepted for the `--fields` flag. Only the minimal fields are printed in this
    release, so extra names are ignored and the view says so.
    """
    lines = [f"status: {result.status.value}"]
    if result.error is not None:
        lines.append(f"error: {result.error.code.value}")
        lines.append(f"  {result.error.message}")
        lines.append(f"help: {result.error.hint}")
        return "\n".join(lines)
    if result.total is None:
        lines.append("counts: unavailable")
    else:
        seconds = result.duration_ms / 1000
        lines.append(
            f"summary: {result.passed} passed, {result.failed} failed, "
            f"{result.skipped} skipped of {result.total} ({seconds:.1f}s)"
        )

    failures = result.failures
    if failures:
        shown = failures[:max_failures]
        lines.append(f"failures[{len(shown)} of {len(failures)}]{{name,file,line,message}}:")
        for failure in shown:
            first = failure.message.splitlines()[0] if failure.message else ""
            message = first
            if not full and len(first) > message_limit:
                message = f"{first[:message_limit]}… ({len(first)} chars total)"
            line = "" if failure.line is None else str(failure.line)
            lines.append(f'  {failure.name},{failure.file or ""},{line},"{message}"')
    else:
        lines.append("failures: none")

    lines.append("flaky: none" if not result.flaky else f"flaky[{len(result.flaky)}]:")
    help_lines = []
    if failures:
        if len(failures) > max_failures:
            help_lines.append(f"  test-adapters run --full    # shows all {len(failures)} failures")
        selectors = " ".join(f.name for f in failures[:max_failures])
        help_lines.append(f"  test-adapters run --select {selectors}    # rerun only these")
    if help_lines:
        lines.append(f"help[{len(help_lines)}]:")
        lines.extend(help_lines)
    return "\n".join(lines)


def combined_text_view(result: CombinedResult, full: bool = False, fields: tuple[str, ...] = ()) -> str:
    """One overall status line, then one block per framework, each headed by its name (5.5)."""
    blocks = [f"status: {result.status.value}"]
    for entry in result.results:
        blocks.append(f"== {entry.framework or 'none'}")
        blocks.append(text_view(entry, full=full, fields=fields))
    return "\n".join(blocks)


def json_view(result: TestResult | CombinedResult) -> str:
    """Complete JSON. Never truncated (criterion 8).

    A CombinedResult writes its derived `status` as a field. Coverage files go through
    `model.wire_coverage`.
    """
    return json.dumps(_to_wire(result), indent=2)


def _to_wire(obj: object) -> object:
    if isinstance(obj, CombinedResult):
        return {
            "schema_version": obj.schema_version,
            "status": obj.status.value,
            "results": [_to_wire(r) for r in obj.results],
        }
    if isinstance(obj, TestResult):
        data = {key: _to_wire(value) for key, value in asdict(obj).items()}
        data["coverage"] = None if obj.coverage is None else wire_coverage(obj.coverage)
        return data
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (tuple, list)):
        return [_to_wire(item) for item in obj]
    if isinstance(obj, Mapping):
        return {str(key): _to_wire(value) for key, value in obj.items()}
    if is_dataclass(obj) and not isinstance(obj, type):
        return {key: _to_wire(value) for key, value in asdict(obj).items()}
    return obj
