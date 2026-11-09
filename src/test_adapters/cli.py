"""Command-line interface (requirements 5.3, 5.4, 5.5).

Exit codes come only from `combine.exit_code_for` and the usage path, so no other module
can invent one (ADR 0002).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from test_adapters import api
from test_adapters.combine import exit_code_for
from test_adapters.config import resolve_config, to_request
from test_adapters.errors import TestAdaptersError, UsageError
from test_adapters.model import CombinedResult, Report, RetryMode, Status, TestResult
from test_adapters.render import combined_text_view, json_view, text_view

EXIT_USAGE = 2
RUN_FLAGS = (
    "--select",
    "--framework",
    "--timeout",
    "--retry-failed",
    "--retry-mode",
    "--coverage",
    "--full",
    "--fields",
    "--json",
    "--result-file",
    "--cwd",
)


class _Parser(argparse.ArgumentParser):
    """argparse that exits with 2 on a usage error and names the valid flags (5.4)."""

    def error(self, message: str) -> None:  # type: ignore[override]
        valid = ", ".join(RUN_FLAGS)
        self.exit(EXIT_USAGE, f"test-adapters: {message}\nvalid run flags: {valid}\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="test-adapters", description="Run pytest or jest and return one normalised result.")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="run the tests and print the default view")
    run_p.add_argument("--select", action="append", default=[], metavar="PATH|NODEID")
    run_p.add_argument("--framework", metavar="NAME|all")
    # Defaults are None so an unset flag falls through to the environment and the config file (7).
    run_p.add_argument("--timeout", type=int, default=None, metavar="SECONDS")
    run_p.add_argument("--retry-failed", type=int, default=None, metavar="N")
    run_p.add_argument("--retry-mode", choices=[m.value for m in RetryMode], default=None)
    run_p.add_argument("--coverage", action="store_true", default=None)
    run_p.add_argument("--full", action="store_true")
    run_p.add_argument("--fields", metavar="LIST")
    run_p.add_argument("--json", action="store_true")
    run_p.add_argument("--result-file", metavar="PATH")
    run_p.add_argument("--cwd", default=".", metavar="DIR")

    sub.add_parser("doctor", help="report framework and reporter availability")

    parse_p = sub.add_parser("parse", help="parse an existing report")
    parse_p.add_argument("framework")
    parse_p.add_argument("report")
    parse_p.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the `test-adapters` command. Returns the process exit code."""
    parser = _build_parser()
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        if args.command is None:
            return _cmd_detect(Path.cwd())
        if args.command == "run":
            return _cmd_run(args)
        if args.command == "doctor":
            return _cmd_doctor(Path.cwd())
        if args.command == "parse":
            return _cmd_parse(args)
        parser.print_help()
        return 0
    except UsageError as exc:
        sys.stderr.write(f"test-adapters: {exc}\n")
        return EXIT_USAGE
    except TestAdaptersError as exc:
        sys.stderr.write(f"test-adapters: {exc}\n")
        return exit_code_for(Status.ERROR)


def _cmd_detect(cwd: Path) -> int:
    """No arguments: detect and doctor, run nothing (5.3, D8)."""
    found = api.detect(cwd)
    report = api.doctor(cwd)
    sys.stdout.write(_doctor_text(report))
    if not found:
        sys.stdout.write("detected: none\nhelp: pass --cwd <dir> or see `test-adapters doctor`\n")
        return 0
    names = ", ".join(f.name for f in found)
    sys.stdout.write(f"detected: {names}\n")
    if len(found) > 1:
        options = " | ".join(f"--framework {f.name}" for f in found)
        sys.stdout.write(f"help: several frameworks detected; choose one of: {options} | --framework all\n")
    return 0


def _cmd_doctor(cwd: Path) -> int:
    sys.stdout.write(_doctor_text(api.doctor(cwd)))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    cwd = Path(args.cwd)
    # Flag, then environment, then config file, then default (7). A bad value raises UsageError (exit 2).
    config = resolve_config(
        cwd,
        {
            "framework": args.framework,
            "timeout_seconds": args.timeout,
            "retry_failed": args.retry_failed,
            "retry_mode": args.retry_mode,
            "coverage": args.coverage,
        },
    )
    request = replace(to_request(config, cwd), select=tuple(args.select))
    # Flags that the skeleton does not implement are refused, not ignored: a silent no-op lies to the caller.
    # The check reads the resolved values, so a config file or environment setting is refused too.
    for flag, used in (
        ("--coverage", config.coverage),
        ("--retry-failed", config.retry_failed),
        ("--retry-mode", config.retry_mode != RetryMode.FILE),
        ("--fields", args.fields),
    ):
        if used:
            raise UsageError(f"{flag} is not implemented in this release (Phase 6)")

    if request.framework == "all":
        result: TestResult | CombinedResult = api.run_all(request)
    else:
        result = api.run(request)

    if args.result_file:
        Path(args.result_file).write_text(json_view(result) + "\n", encoding="utf-8")
    if args.json:
        sys.stdout.write(json_view(result) + "\n")
    elif isinstance(result, CombinedResult):
        sys.stdout.write(combined_text_view(result, full=args.full) + "\n")
    else:
        sys.stdout.write(text_view(result, full=args.full) + "\n")
    return exit_code_for(result.status)


def _cmd_parse(args: argparse.Namespace) -> int:
    result = api.parse(args.framework, Path(args.report))
    if args.json:
        sys.stdout.write(json_view(result) + "\n")
    else:
        sys.stdout.write(text_view(result) + "\n")
    return exit_code_for(result.status)


def _doctor_text(report: Report) -> str:
    lines = []
    for entry in report.frameworks:
        state = "available" if entry.available else "missing"
        detected = "detected" if entry.detected else "not detected"
        lines.append(f"framework: {entry.name} {state}, {detected}")
        if entry.hint:
            lines.append(f"  help: {entry.hint}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
