"""Default text view rules (requirements 5.5, criteria 7, 8 and 11) and the `--fields` flag.

The view tests build TestResult values by hand. The CLI tests stub `api.run`, so no test runs.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from test_adapters import cli
from test_adapters.config import ENV_PREFIX
from test_adapters.errors import UsageError
from test_adapters.model import CombinedResult, Failure, RawInfo, Status, TestRequest, TestResult
from test_adapters.render import FAILURE_LIMIT, MESSAGE_LIMIT, combined_text_view, json_view, parse_fields, text_view

LONG_MESSAGE = "x" * 5000  # one line, 5,000 characters (criterion 8)


class _Stop(Exception):
    """Raised by the fake run when a test must not reach the engine."""


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name)


def make_result(failures: tuple[Failure, ...] = ()) -> TestResult:
    failed = len(failures)
    return TestResult(
        framework="pytest",
        status=Status.FAILED if failed else Status.PASSED,
        error=None,
        total=3 + failed,
        passed=3,
        failed=failed,
        skipped=0,
        errors=0,
        duration_ms=1500,
        failures=failures,
        flaky=(),
        coverage=None,
        warnings=(),
        degraded=False,
        raw=RawInfo(exit_code=1 if failed else 0, stdout_path=None, report_path=None),
        command="pytest",
    )


def long_failure() -> Failure:
    return Failure(name="tests/test_long.py::test_long", message=LONG_MESSAGE, file="tests/test_long.py", line=7)


def many_failures(count: int) -> tuple[Failure, ...]:
    return tuple(Failure(name=f"t::test_{i}", message="boom", file="t.py", line=i) for i in range(count))


# Message cut (5.5 truncation, criterion 8)


def test_default_view_cuts_a_long_message_at_200_characters() -> None:
    view = text_view(make_result((long_failure(),)))
    assert f"{'x' * MESSAGE_LIMIT}… (5000 chars total)" in view
    assert "x" * (MESSAGE_LIMIT + 1) not in view


def test_full_view_keeps_the_whole_message() -> None:
    view = text_view(make_result((long_failure(),)), full=True)
    assert LONG_MESSAGE in view
    assert "chars total" not in view


def test_json_view_is_never_truncated() -> None:
    data = json.loads(json_view(make_result((long_failure(),))))
    assert data["failures"][0]["message"] == LONG_MESSAGE


def test_combined_view_cuts_a_long_message_per_framework() -> None:
    combined = CombinedResult(results=(make_result((long_failure(),)),))
    view = combined_text_view(combined)
    assert f"{'x' * MESSAGE_LIMIT}… (5000 chars total)" in view
    assert combined_text_view(combined, full=True).count(LONG_MESSAGE) == 1


# Definitive empty state (5.5)


def test_passing_run_prints_failures_none_and_flaky_none() -> None:
    view = text_view(make_result())
    assert "failures: none" in view
    assert "flaky: none" in view
    assert "failures[" not in view


# Failure limit (5.5, criterion 7)


def test_failing_run_lists_at_most_twenty_with_n_of_total() -> None:
    view = text_view(make_result(many_failures(25)))
    assert f"failures[{FAILURE_LIMIT} of 25]" in view
    listed = [line for line in view.splitlines() if line.startswith("  t::test_")]
    assert len(listed) == FAILURE_LIMIT


def test_failure_limit_help_points_to_json_for_the_rest() -> None:
    # `--full` lifts the message cut, not the failure limit. The help line must name a command that shows all.
    view = text_view(make_result(many_failures(25)))
    help_line = next(line for line in view.splitlines() if "shows all 25 failures" in line)
    assert "--json" in help_line
    assert "--full" not in help_line


# Extra fields (`--fields`)


@dataclass(frozen=True)
class TimedFailure(Failure):
    """A failure with one extra field, to show that `fields` renders any field the model carries."""

    duration_ms: int = 0


def test_extra_field_adds_a_column_to_the_header_and_to_each_failure_line() -> None:
    failure = TimedFailure(name="t::t", message="boom", file="t.py", line=3, duration_ms=250)
    result = make_result((failure,))
    assert "{name,file,line,message}" in text_view(result)
    view = text_view(result, fields=("duration_ms",))
    assert "{name,file,line,message,duration_ms}" in view
    assert 't::t,t.py,3,"boom",250' in view


def test_fields_already_in_the_default_view_add_no_column() -> None:
    result = make_result((Failure(name="t::t", message="boom", file="t.py", line=3),))
    assert text_view(result, fields=("file", "line")) == text_view(result)


def test_parse_fields_accepts_the_failure_field_names() -> None:
    assert parse_fields("name,file") == ("name", "file")
    assert parse_fields("line") == ("line",)


def test_parse_fields_strips_spaces_around_names() -> None:
    assert parse_fields("file, line") == ("file", "line")


def test_parse_fields_keeps_a_repeated_name_once() -> None:
    assert parse_fields("line,file,line") == ("line", "file")


def test_parse_fields_rejects_an_unknown_name_and_lists_the_valid_ones() -> None:
    with pytest.raises(UsageError, match="unknown field 'duration'") as info:
        parse_fields("file,duration")
    assert "valid fields: name, message, file, line" in str(info.value)


def test_parse_fields_rejects_an_empty_name() -> None:
    with pytest.raises(UsageError, match="unknown field ''"):
        parse_fields("file,,line")


# CLI wiring


def run_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, result: TestResult | None, *flags: str) -> int:
    def fake_run(request: TestRequest) -> TestResult:
        if result is None:
            raise _Stop()
        return result

    monkeypatch.setattr(cli.api, "run", fake_run)
    return cli.main(["run", "--cwd", str(tmp_path), "--framework", "pytest", *flags])


def test_cli_unknown_field_is_a_usage_error_before_any_test_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # result None: if a run started, the fake would raise _Stop, which the CLI does not catch.
    code = run_cli(monkeypatch, tmp_path, None, "--fields", "duration")
    assert code == 2
    assert "unknown field 'duration'" in capsys.readouterr().err


def test_cli_known_fields_are_accepted_and_not_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run_cli(monkeypatch, tmp_path, make_result(), "--fields", "file,line")
    assert code == 0
    assert "not implemented" not in capsys.readouterr().err


def test_cli_five_thousand_character_failure_default_and_full_view(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Evidence for the card: the default view of a 5,000-character failure, then the complete `--full` view.
    code = run_cli(monkeypatch, tmp_path, make_result((long_failure(),)))
    assert code == 1
    default_out = capsys.readouterr().out
    assert f"{'x' * MESSAGE_LIMIT}… (5000 chars total)" in default_out
    assert "x" * (MESSAGE_LIMIT + 1) not in default_out

    code = run_cli(monkeypatch, tmp_path, make_result((long_failure(),)), "--full")
    assert code == 1
    assert LONG_MESSAGE in capsys.readouterr().out


def test_cli_json_is_complete_for_a_long_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_cli(monkeypatch, tmp_path, make_result((long_failure(),)), "--json")
    data = json.loads(capsys.readouterr().out)
    assert data["failures"][0]["message"] == LONG_MESSAGE
