"""jest adapter (requirements 4.2, 4.3, 6.1, 6.2, 6.3, 6.4).

`run` is `npx --no-install jest --json --outputFile=<report>`. `--no-install` makes npx refuse to
download jest, so a run never fetches code without the owner's approval. A project without a local
jest gets `tool_missing`.

Facts below were observed live on jest 29.7.0 and 30.5.2 (docs/live-checks/jest.md and the T13 probes):

- `testResults[].name` is an absolute path. `testResults` order is not stable, so nothing here relies on it.
- Test status is passed, failed, pending, todo (skipped and disabled are accepted too, never seen).
  Pending, todo, skipped and disabled count as skipped (4.2). Any other status is an unparseable report.
- A suite that fails to load, and an `afterAll` that throws, both carry `Test suite failed to run` in the
  suite `message`. The first has no `assertionResults`. The second keeps its tests, which show as passed.
  Both are collection errors, and the counts are not trusted (4.3). A throwing `beforeAll` is different:
  its tests fail, there is no marker, and it is a normal failed run.
- `-t` is a case-insensitive regex over `fullName`, the titles joined by one space. A pattern that
  matches nothing exits 0 with every test pending, so exit 0 does not show that a selected test ran.
- Two tests can share a `fullName` (`A B` > `c` and `A` > `B c`). `-t` then runs both.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Sequence

from test_adapters.adapters.base import Command
from test_adapters.errors import AdapterError
from test_adapters.model import (
    ErrorCode,
    ErrorInfo,
    Failure,
    RawInfo,
    Status,
    TestRequest,
    TestResult,
)

COMMAND = "npx --no-install jest"
# Work-directory files. The run state carries what build_command knew to parse (project root, selection).
_REPORT = "jest-report.json"
_STATE = "jest-run.json"

_LOAD_FAILURE_MARKER = "Test suite failed to run"
_NPX_REFUSED = "npx canceled due to missing packages"
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_REGEX_SPECIAL = re.compile(r"[.*+?^${}()|\[\]\\]")
# `at fn (path:line:col)` or `at path:line:col`. The path may hold a drive colon, so it ends at the digits.
_FRAME = re.compile(r"^\s*at (?:[^()]*\()?(?P<path>.+?):(?P<line>\d+):(?P<col>\d+)\)?\s*$")
_STACK_START = re.compile(r"\n\s+at ")
_RAN = ("passed", "failed")
_SKIPPED = ("pending", "todo", "skipped", "disabled")
_MESSAGE_LIMIT = 2000
_NO_COVERAGE = "coverage is not measured for jest in this release, so coverage is null"


class JestAdapter:
    name = "jest"
    command_template = "npx --no-install jest --json --outputFile={report} {select}"
    report_format = "jest-json"

    def detect(self, cwd: Path) -> bool:
        """jest.config.*, or package.json with a jest key, or jest in scripts or devDependencies."""
        if any(cwd.glob("jest.config.*")):
            return True
        package = cwd / "package.json"
        if not package.is_file():
            return False
        try:
            data = json.loads(package.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if not isinstance(data, dict):
            return False
        if "jest" in data:
            return True
        scripts = data.get("scripts")
        if isinstance(scripts, dict) and any("jest" in str(value) for value in scripts.values()):
            return True
        dev = data.get("devDependencies")
        return isinstance(dev, dict) and "jest" in dev

    def build_command(self, request: TestRequest, workdir: Path) -> Command:
        """`--json --outputFile=<file>` plus the selection (6.4).

        A file path goes to `--runTestsByPath`. `file::A > b` goes to `--runTestsByPath <file> -t
        '^<escaped fullName>$'`. Several names in one file join into one `-t` pattern. Anything else
        (a name in several files, a mix of paths and names, a missing file) is `unsupported_selector`.
        """
        root = request.cwd.resolve()
        files, names = _selection(root, request.select)
        report = workdir / _REPORT
        state = workdir / _STATE
        argv: list[str] = [_npx(), "--no-install", "jest", "--json", f"--outputFile={report}"]
        if isinstance(request.parallelism, int):
            argv.append(f"--maxWorkers={request.parallelism}")
        if names:
            argv += ["-t", _pattern([_full_name(title) for _, title in names])]
        run_files = [*files, *dict.fromkeys(file for file, _ in names)]
        if run_files:
            argv += ["--runTestsByPath", *run_files]
        state.write_text(
            json.dumps(
                {
                    "root": str(root),
                    "select": [{"file": file, "name": title} for file, title in names],
                    "coverage": request.coverage,
                }
            ),
            encoding="utf-8",
        )
        return Command(argv=tuple(argv), env=dict(request.env), report_paths=(report, state))

    def parse(self, report_files: Sequence[Path], exit_code: int | None, stdout: str, timed_out: bool) -> TestResult:
        """The jest JSON report. Suites that fail to load map to ERROR/collection (4.2, 4.3).

        With no report: a timeout is `timeout` with null counts (stdout is not read for counts), an npx
        refusal is `tool_missing`, anything else is `unparseable_report`.
        """
        report = next((p for p in report_files if p.name != _STATE and p.is_file()), None)
        state = _read_state(report_files, report)
        root = Path(str(state.get("root") or Path.cwd())).resolve()
        warnings = (_NO_COVERAGE,) if state.get("coverage") else ()
        if report is None:
            if timed_out:
                return _timeout(exit_code, warnings)
            if _NPX_REFUSED in stdout:
                return _error(
                    ErrorCode.TOOL_MISSING,
                    "npx could not find jest in the project",
                    "install jest in the project (npm install --save-dev jest); test-adapters never downloads it",
                    exit_code,
                    warnings,
                )
            return _error(
                ErrorCode.UNPARSEABLE_REPORT,
                f"no jest report was written (exit code {exit_code})",
                "run the command by hand and read the output",
                exit_code,
                warnings,
            )
        try:
            suites = _suites(json.loads(report.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            return _error(
                ErrorCode.UNPARSEABLE_REPORT,
                f"jest report is malformed: {exc}",
                "run the command by hand and read the output",
                exit_code,
                warnings,
            )

        broken = [s for s in suites if _load_failed(s)]
        if broken:
            first = broken[0]
            return _error(
                ErrorCode.COLLECTION,
                f"{_relative(root, str(first['name']))}: {_clean(str(first.get('message') or ''))}",
                "fix the import or syntax error first",
                exit_code,
                warnings,
                report,
            )

        failures: list[Failure] = []
        passed = failed = skipped = 0
        ran: dict[tuple[str, str], int] = {}  # (file, lower fullName) -> tests that ran
        clashes: dict[tuple[str, str], int] = {}  # (file, lower fullName) -> tests with that name
        duration = 0
        for suite in suites:
            file = _relative(root, str(suite["name"]))
            duration += _suite_ms(suite)
            for item in suite["assertionResults"]:
                key = (file, str(item["fullName"]).lower())
                clashes[key] = clashes.get(key, 0) + 1
                status = item.get("status")
                if status in _RAN:
                    ran[key] = ran.get(key, 0) + 1
                if status == "passed":
                    passed += 1
                elif status == "failed":
                    failed += 1
                elif status in _SKIPPED:
                    skipped += 1
                else:
                    return _error(
                        ErrorCode.UNPARSEABLE_REPORT,
                        f"jest reported the unknown test status {status!r} for {file}",
                        "run the command by hand and read the output",
                        exit_code,
                        warnings,
                        report,
                    )

        total = passed + failed + skipped
        if total == 0:
            return _error(
                ErrorCode.NO_TESTS,
                "the report contains no tests",
                "check the test file pattern and the selection",
                exit_code,
                warnings,
                report,
            )

        missing = [
            f"{entry['file']}::{entry['name']}"
            for entry in state.get("select", [])
            if (entry["file"], _full_name(entry["name"]).lower()) not in ran
        ]
        if missing:
            # Exit 0 with every test pending is how jest answers a pattern that matches nothing.
            return _error(
                ErrorCode.NO_TESTS,
                "selected test did not run: " + "; ".join(missing),
                "check the file and the title; a skipped test counts as not run",
                exit_code,
                warnings,
                report,
            )

        notes: list[str] = list(warnings)
        for entry in state.get("select", []):
            key = (entry["file"], _full_name(entry["name"]).lower())
            if ran[key] > 1:
                notes.append(
                    f"selecting {entry['file']}::{entry['name']} ran {ran[key]} tests, "
                    "because their fullName is the same (jest -t ignores case and nesting)"
                )
        for suite in suites:
            file = _relative(root, str(suite["name"]))
            for item in suite["assertionResults"]:
                if item.get("status") != "failed":
                    continue
                name = f"{file}::{' > '.join([*map(str, item.get('ancestorTitles') or []), str(item['title'])])}"
                texts = [_clean(str(m)) for m in item.get("failureMessages") or []]
                line = _first_line_in(root, Path(str(suite["name"])), texts)
                failures.append(Failure(name=name, message=_summary(texts), file=file, line=line))
                if line is None:
                    notes.append(f"{name}: no stack frame points at {file}, so line is null")
                if clashes[(file, str(item["fullName"]).lower())] > 1:
                    notes.append(
                        f"{name} shares its fullName with another test in {file}, so jest -t cannot select it alone"
                    )

        return TestResult(
            framework="jest",
            status=Status.FAILED if failed else Status.PASSED,
            error=None,
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=0,
            duration_ms=duration,
            failures=tuple(failures),
            flaky=(),
            coverage=None,
            warnings=tuple(notes),
            degraded=False,
            raw=RawInfo(exit_code=exit_code, stdout_path=None, report_path=str(report)),
            command=COMMAND,
        )

    def requires(self) -> Sequence[str]:
        """`npx` on PATH. It resolves the project's local jest, so jest need not be global."""
        return ("npx",)


def _npx() -> str:
    """The full path to npx, so Windows finds `npx.cmd`. Falls back to the bare name."""
    return shutil.which("npx") or "npx"


def _selection(root: Path, select: Sequence[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """Split `select` into file paths and `(file, title)` names, or raise `unsupported_selector` (6.4)."""
    files: list[str] = []
    names: list[tuple[str, str]] = []
    for item in select:
        path, sep, title = item.partition("::")
        if not path.strip() or path.startswith("-") or not (root / path).is_file():
            raise _unsupported(item, "the file does not exist in the project")
        if sep and not title.strip():
            raise _unsupported(item, "the title after :: is empty")
        if sep:
            names.append((_relative(root, str((root / path).resolve())), title))
        else:
            files.append(path)
    if files and names:
        raise _unsupported(", ".join(select), "file paths and test names cannot be mixed")
    if len({file for file, _ in names}) > 1:
        raise _unsupported(
            ", ".join(select), "jest can select names in one file per run; run each file on its own"
        )
    return files, names


def _unsupported(item: str, reason: str) -> AdapterError:
    return AdapterError(
        ErrorCode.UNSUPPORTED_SELECTOR,
        f"jest cannot select {item!r}: {reason}",
        "use a file path, or file::Describe > test title for tests in one file",
    )


def _full_name(title: str) -> str:
    """jest's `fullName`: the titles joined by a single space. `A > b` becomes `A b`."""
    return " ".join(title.split(" > "))


def _pattern(full_names: Sequence[str]) -> str:
    """The `-t` regex: each fullName escaped, anchored at both ends."""
    escaped = [_REGEX_SPECIAL.sub(lambda m: "\\" + m.group(0), name) for name in full_names]
    return f"^{escaped[0]}$" if len(escaped) == 1 else f"^(?:{'|'.join(escaped)})$"


def _read_state(report_files: Sequence[Path], report: Path | None) -> dict[str, Any]:
    """The run state beside the report, or empty when the report is a saved file (names then use the cwd)."""
    candidates = [p for p in report_files if p.name == _STATE]
    if report is not None:
        candidates.append(report.parent / _STATE)
    for candidate in candidates:
        if candidate.is_file():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict):
                return data
    return {}


def _suites(data: Any) -> list[dict[str, Any]]:
    """The suites of a report, checked for the fields parse reads. ValueError when the shape is wrong."""
    if not isinstance(data, dict) or not isinstance(data.get("testResults"), list):
        raise ValueError("no testResults list")
    suites: list[dict[str, Any]] = []
    for suite in data["testResults"]:
        if not isinstance(suite, dict) or not isinstance(suite.get("name"), str):
            raise ValueError("a suite has no name")
        items = suite.get("assertionResults")
        if not isinstance(items, list):
            raise ValueError("a suite has no assertionResults list")
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("title"), str):
                raise ValueError("a test has no title")
            item.setdefault("fullName", " ".join([*map(str, item.get("ancestorTitles") or []), item["title"]]))
        suites.append(suite)
    return suites


def _load_failed(suite: dict[str, Any]) -> bool:
    """A suite that did not load, or whose hook broke after the tests (`afterAll`). Never a failed test."""
    if _LOAD_FAILURE_MARKER in str(suite.get("message") or ""):
        return True
    return suite.get("status") == "failed" and not suite["assertionResults"]


def _suite_ms(suite: dict[str, Any]) -> int:
    stats = suite.get("perfStats")
    if isinstance(stats, dict) and isinstance(stats.get("start"), int) and isinstance(stats.get("end"), int):
        start: int = stats["start"]
        end: int = stats["end"]
        return max(0, end - start)
    return 0


def _relative(root: Path, name: str) -> str:
    """`name` relative to the project root with forward slashes, or the resolved path when outside it."""
    path = Path(name)
    path = (path if path.is_absolute() else root / path).resolve()
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _first_line_in(root: Path, test_file: Path, texts: Sequence[str]) -> int | None:
    """The line of the first `at <path>:<line>:<col>` frame that points at the test file (6.2)."""
    target = _resolved(root, str(test_file))
    for text in texts:
        for raw in text.splitlines():
            match = _FRAME.match(raw)
            if match is not None and _resolved(root, match.group("path")) == target:
                return int(match.group("line"))
    return None


def _resolved(root: Path, name: str) -> Path:
    path = Path(name)
    return (path if path.is_absolute() else root / path).resolve()


def _clean(text: str) -> str:
    """Without colour codes, trimmed and cut to a length a result can carry."""
    text = _ANSI.sub("", text).strip()
    return text if len(text) <= _MESSAGE_LIMIT else text[:_MESSAGE_LIMIT] + "..."


def _summary(texts: Sequence[str]) -> str:
    """The failure text up to the first stack frame."""
    if not texts:
        return ""
    return _STACK_START.split(texts[0], maxsplit=1)[0].strip()


def _timeout(exit_code: int | None, warnings: tuple[str, ...]) -> TestResult:
    """A killed run with no report (6.3). Every count is null, never 0, and stdout is not read for counts."""
    return TestResult(
        framework="jest",
        status=Status.TIMEOUT,
        error=None,
        total=None,
        passed=None,
        failed=None,
        skipped=None,
        errors=None,
        duration_ms=0,
        failures=(),
        flaky=(),
        coverage=None,
        warnings=warnings,
        degraded=False,
        raw=RawInfo(exit_code=exit_code, stdout_path=None, report_path=None),
        command=COMMAND,
    )


def _error(
    code: ErrorCode,
    message: str,
    hint: str,
    exit_code: int | None,
    warnings: tuple[str, ...] = (),
    report: Path | None = None,
) -> TestResult:
    return TestResult(
        framework="jest",
        status=Status.ERROR,
        error=ErrorInfo(code=code, message=message, hint=hint),
        total=None,
        passed=None,
        failed=None,
        skipped=None,
        errors=None,
        duration_ms=0,
        failures=(),
        flaky=(),
        coverage=None,
        warnings=warnings,
        degraded=False,
        raw=RawInfo(exit_code=exit_code, stdout_path=None, report_path=str(report) if report else None),
        command=COMMAND,
    )
