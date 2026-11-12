"""jest adapter (requirements 4.2, 4.3, 6.2, 6.3, 6.4; issue #31).

Two kinds of test:

- Synthetic reports. Each test writes a jest JSON report by hand and parses it, with no jest needed.
  They cover status mapping, names, lines, collection, timeout, selection and warnings.
- Live runs. Each test runs a real jest on a small project. They need jest and skip with a reason when
  jest cannot be run. Set JEST_NODE_MODULES to a node_modules folder that holds jest, for example one from
  `npm install --save-dev jest@29` in a scratch folder outside the repo. The folder is symlinked into a
  temporary copy of the project, so nothing is written to the repo. jest is run as
  `npx --no-install jest`, so no test downloads jest.

The live checks ran on jest 29.7.0 and 30.5.2 (docs/live-checks/jest.md). Run the module once with each
version and compare the two summaries.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from test_adapters import api
from test_adapters.adapters.jest_adapter import JestAdapter
from test_adapters.errors import AdapterError
from test_adapters.model import ErrorCode, Status, TestRequest, TestResult

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "jest_mixed"
JEST_NODE_MODULES_ENV = "JEST_NODE_MODULES"


# ---------------------------------------------------------------- synthetic reports (no jest needed)


def _assertion(
    title: str, *, ancestors: tuple[str, ...] = (), status: str = "passed", messages: tuple[str, ...] = ()
) -> dict:
    return {
        "ancestorTitles": list(ancestors),
        "title": title,
        "fullName": " ".join([*ancestors, title]),
        "status": status,
        "failureMessages": list(messages),
        "location": None,
    }


def _suite(
    path: Path,
    assertions: list[dict],
    *,
    status: str = "passed",
    message: str = "",
    start: int = 0,
    end: int = 0,
) -> dict:
    return {
        "name": str(path),
        "status": status,
        "assertionResults": assertions,
        "message": message,
        "perfStats": {"start": start, "end": end},
    }


def _report(*suites: dict) -> dict:
    return {"success": True, "testResults": list(suites)}


def _root(tmp_path: Path) -> Path:
    """A project folder with three empty test files, so selectors that name them are valid."""
    root = tmp_path / "project"
    (root / "tests").mkdir(parents=True, exist_ok=True)
    for name in ("a.test.js", "b.test.js", "cart.test.js"):
        (root / "tests" / name).write_text("", encoding="utf-8")
    return root


def _run(
    tmp_path: Path,
    root: Path,
    *,
    select: tuple[str, ...] = (),
    report: dict | None = None,
    raw: str | None = None,
    exit_code: int | None = 1,
    stdout: str = "",
    timed_out: bool = False,
    coverage: bool = False,
) -> TestResult:
    """build_command for the request, write the report where jest would, then parse as run does."""
    workdir = tmp_path / "work"
    workdir.mkdir(exist_ok=True)
    adapter = JestAdapter()
    command = adapter.build_command(TestRequest(cwd=root, framework="jest", select=select, coverage=coverage), workdir)
    if report is not None:
        command.report_paths[0].write_text(json.dumps(report), encoding="utf-8")
    if raw is not None:
        command.report_paths[0].write_text(raw, encoding="utf-8")
    return adapter.parse(list(command.report_paths), exit_code, stdout, timed_out)


def _counts(result: TestResult) -> tuple[int | None, ...]:
    return (result.total, result.passed, result.failed, result.skipped, result.errors)


def _argv_after(argv: tuple[str, ...], flag: str) -> str:
    return argv[argv.index(flag) + 1]


def test_command_runs_npx_no_install_with_json_and_outputfile(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    command = JestAdapter().build_command(TestRequest(cwd=_root(tmp_path)), workdir)

    assert Path(command.argv[0]).name.lower().startswith("npx")
    assert command.argv[1:4] == ("--no-install", "jest", "--json")
    assert command.argv[4] == f"--outputFile={command.report_paths[0]}"
    assert "-t" not in command.argv and "--runTestsByPath" not in command.argv


def test_command_template_says_no_install() -> None:
    assert JestAdapter.command_template.startswith("npx --no-install jest ")


def test_file_path_select_uses_runtestsbypath(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    command = JestAdapter().build_command(TestRequest(cwd=_root(tmp_path), select=("tests/a.test.js",)), workdir)

    assert command.argv[-2:] == ("--runTestsByPath", "tests/a.test.js")
    assert "-t" not in command.argv


def test_several_file_paths_go_in_one_runtestsbypath(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    command = JestAdapter().build_command(
        TestRequest(cwd=_root(tmp_path), select=("tests/a.test.js", "tests/b.test.js")), workdir
    )

    assert command.argv[-3:] == ("--runTestsByPath", "tests/a.test.js", "tests/b.test.js")


def test_name_select_escapes_the_fullname_into_the_t_pattern(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    command = JestAdapter().build_command(
        TestRequest(cwd=_root(tmp_path), select=("tests/cart.test.js::Cart > adds (item) [x] $",)), workdir
    )

    assert _argv_after(command.argv, "-t") == r"^Cart adds \(item\) \[x\] \$$"
    assert _argv_after(command.argv, "--runTestsByPath") == "tests/cart.test.js"


def test_several_names_in_one_file_are_joined_into_one_pattern(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    command = JestAdapter().build_command(
        TestRequest(cwd=_root(tmp_path), select=("tests/a.test.js::A > b", "tests/a.test.js::C > d")), workdir
    )

    assert _argv_after(command.argv, "-t") == r"^(?:A b|C d)$"


@pytest.mark.parametrize(
    "select",
    [
        ("",),
        ("::Cart > adds",),
        ("tests/a.test.js::",),
        ("tests/a.test.js::   ",),
        ("tests/missing.test.js",),
        ("tests/a.test.js", "tests/b.test.js::X"),
        ("tests/a.test.js::A", "tests/b.test.js::B"),
    ],
)
def test_selectors_jest_cannot_express_are_unsupported(tmp_path: Path, select: tuple[str, ...]) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    with pytest.raises(AdapterError) as info:
        JestAdapter().build_command(TestRequest(cwd=_root(tmp_path), select=select), workdir)

    assert info.value.code is ErrorCode.UNSUPPORTED_SELECTOR


def test_integer_parallelism_becomes_max_workers(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    fixed = JestAdapter().build_command(TestRequest(cwd=_root(tmp_path), parallelism=2), workdir)
    auto = JestAdapter().build_command(TestRequest(cwd=_root(tmp_path), parallelism="auto"), workdir)

    assert "--maxWorkers=2" in fixed.argv
    assert not any(arg.startswith("--maxWorkers") for arg in auto.argv)


def test_request_env_is_passed_to_the_command(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    command = JestAdapter().build_command(TestRequest(cwd=_root(tmp_path), env={"JEST_X": "1"}), workdir)

    assert command.env["JEST_X"] == "1"


def test_every_status_maps_to_the_4_2_outcome(tmp_path: Path) -> None:
    root = _root(tmp_path)
    file = root / "tests" / "a.test.js"
    report = _report(
        _suite(
            file,
            [
                _assertion("p", status="passed"),
                _assertion("f", status="failed", messages=(f"Error\n    at Object.toBe ({file}:3:5)",)),
                _assertion("pe", status="pending"),
                _assertion("td", status="todo"),
                _assertion("sk", status="skipped"),
                _assertion("di", status="disabled"),
            ],
            status="failed",
        )
    )
    result = _run(tmp_path, root, report=report)

    assert _counts(result) == (6, 1, 1, 4, 0)
    assert result.status is Status.FAILED
    assert result.error is None


def test_unknown_test_status_is_unparseable_not_counted(tmp_path: Path) -> None:
    root = _root(tmp_path)
    report = _report(_suite(root / "tests" / "a.test.js", [_assertion("x", status="weird")]))
    result = _run(tmp_path, root, report=report)

    assert result.status is Status.ERROR
    assert result.error is not None and result.error.code is ErrorCode.UNPARSEABLE_REPORT
    assert _counts(result) == (None,) * 5


def test_failure_name_file_and_line_come_from_the_first_frame_in_the_test_file(tmp_path: Path) -> None:
    root = _root(tmp_path)
    file = root / "tests" / "cart.test.js"
    helper = root / "src" / "util.js"
    message = "\n".join(
        [
            "expect(received).toBe(expected)",
            f"    at helper ({helper}:2:9)",
            f"    at Object.toBe ({file}:8:15)",
            f"    at Promise.then.completed ({file}:12:1)",
        ]
    )
    report = _report(
        _suite(
            file,
            [_assertion("adds item", ancestors=("Cart",), status="failed", messages=(message,))],
            status="failed",
        )
    )
    result = _run(tmp_path, root, report=report)

    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.name == "tests/cart.test.js::Cart > adds item"
    assert failure.file == "tests/cart.test.js"
    assert failure.line == 8
    assert "expect(received).toBe(expected)" in failure.message


def test_failure_line_is_none_when_no_frame_points_at_the_file(tmp_path: Path) -> None:
    root = _root(tmp_path)
    file = root / "tests" / "a.test.js"
    message = f"Error\n    at helper ({root / 'src' / 'util.js'}:2:9)"
    report = _report(_suite(file, [_assertion("x", status="failed", messages=(message,))], status="failed"))
    result = _run(tmp_path, root, report=report)

    assert result.failures[0].file == "tests/a.test.js"
    assert result.failures[0].line is None


def test_frame_with_a_path_relative_to_the_project_is_matched(tmp_path: Path) -> None:
    root = _root(tmp_path)
    file = root / "tests" / "a.test.js"
    message = "Error\n    at Object.toBe (tests/a.test.js:8:15)"
    report = _report(_suite(file, [_assertion("x", status="failed", messages=(message,))], status="failed"))
    result = _run(tmp_path, root, report=report)

    assert result.failures[0].line == 8


def test_frame_without_parentheses_is_matched(tmp_path: Path) -> None:
    root = _root(tmp_path)
    file = root / "tests" / "a.test.js"
    message = f"Error\n    at {file}:5:1"
    report = _report(_suite(file, [_assertion("x", status="failed", messages=(message,))], status="failed"))

    assert _run(tmp_path, root, report=report).failures[0].line == 5


def test_load_failure_is_collection_error_and_never_counted(tmp_path: Path) -> None:
    root = _root(tmp_path)
    broken = _suite(
        root / "tests" / "a.test.js",
        [],
        status="failed",
        message="  ● Test suite failed to run\n\n    Jest encountered an unexpected token\n\n    Details:\n",
    )
    other = _suite(root / "tests" / "b.test.js", [_assertion("one"), _assertion("two")])
    result = _run(tmp_path, root, report=_report(other, broken))

    assert result.status is Status.ERROR
    assert result.error is not None and result.error.code is ErrorCode.COLLECTION
    assert "tests/a.test.js" in result.error.message
    assert "Jest encountered an unexpected token" in result.error.message
    assert _counts(result) == (None,) * 5


def test_suite_failure_with_no_failed_test_is_collection_not_green(tmp_path: Path) -> None:
    # An afterAll that throws leaves a passing test and a suite marked failed. That is not a green run.
    root = _root(tmp_path)
    report = _report(
        _suite(
            root / "tests" / "a.test.js",
            [_assertion("p")],
            status="failed",
            message="  ● Test suite failed to run\n\n    afterAll broke\n",
        )
    )
    result = _run(tmp_path, root, report=report, exit_code=1)

    assert result.status is Status.ERROR
    assert result.error is not None and result.error.code is ErrorCode.COLLECTION
    assert "afterAll broke" in result.error.message
    assert _counts(result) == (None,) * 5


def test_hook_failure_is_failed_tests_not_a_load_failure(tmp_path: Path) -> None:
    root = _root(tmp_path)
    file = root / "tests" / "a.test.js"
    message = f"beforeAll broke\n    at Object.<anonymous> ({file}:3:11)"
    report = _report(
        _suite(
            file,
            [
                _assertion("a", ancestors=("Hook",), status="failed", messages=(message,)),
                _assertion("b", ancestors=("Hook",), status="failed", messages=(message,)),
            ],
            status="failed",
            message="  ● Hook\n\n    beforeAll broke\n",
        )
    )
    result = _run(tmp_path, root, report=report)

    assert result.status is Status.FAILED
    assert result.error is None
    assert _counts(result) == (2, 0, 2, 0, 0)


def test_report_with_no_tests_is_no_tests_error(tmp_path: Path) -> None:
    result = _run(tmp_path, _root(tmp_path), report=_report())

    assert result.error is not None and result.error.code is ErrorCode.NO_TESTS
    assert _counts(result) == (None,) * 5


def test_no_report_and_no_timeout_is_unparseable(tmp_path: Path) -> None:
    result = _run(tmp_path, _root(tmp_path), exit_code=1, stdout="some output")

    assert result.error is not None and result.error.code is ErrorCode.UNPARSEABLE_REPORT
    assert _counts(result) == (None,) * 5


def test_npx_refusing_to_install_jest_is_tool_missing(tmp_path: Path) -> None:
    stdout = 'npm error npx canceled due to missing packages and no YES option: ["jest@30.5.2"]\n'
    result = _run(tmp_path, _root(tmp_path), exit_code=1, stdout=stdout)

    assert result.error is not None and result.error.code is ErrorCode.TOOL_MISSING
    assert "jest" in result.error.hint
    assert _counts(result) == (None,) * 5


def test_timeout_without_report_has_null_counts_and_reads_no_stdout(tmp_path: Path) -> None:
    progress = " PASS  tests/a.test.js\n  ✓ adds item (2 ms)\n  ✓ removes item (1 ms)\n"
    result = _run(tmp_path, _root(tmp_path), exit_code=None, stdout=progress, timed_out=True)

    assert result.status is Status.TIMEOUT
    assert result.error is None
    assert _counts(result) == (None,) * 5
    assert result.degraded is False


def test_malformed_report_is_unparseable(tmp_path: Path) -> None:
    result = _run(tmp_path, _root(tmp_path), raw="{not json")

    assert result.error is not None and result.error.code is ErrorCode.UNPARSEABLE_REPORT
    assert _counts(result) == (None,) * 5


def test_failed_test_whose_fullname_is_shared_in_its_file_gets_a_warning(tmp_path: Path) -> None:
    # 'A B' > 'c' and 'A' > 'B c' both have fullName 'A B c' (6.4). Only the failing one is reported.
    root = _root(tmp_path)
    file = root / "tests" / "a.test.js"
    message = f"Error\n    at Object.toBe ({file}:8:15)"
    report = _report(
        _suite(
            file,
            [
                _assertion("c", ancestors=("A B",), status="passed"),
                _assertion("B c", ancestors=("A",), status="failed", messages=(message,)),
                _assertion("unique", ancestors=("Cart",), status="failed", messages=(message,)),
            ],
            status="failed",
        )
    )
    result = _run(tmp_path, root, report=report)

    assert [w for w in result.warnings if "tests/a.test.js::A > B c" in w]
    assert not [w for w in result.warnings if "Cart > unique" in w]
    assert len(result.warnings) == 1


def test_fullname_clash_is_checked_ignoring_case(tmp_path: Path) -> None:
    # jest's -t ignores case, so 'Case adds item' and 'Case ADDS ITEM' cannot be told apart by name (6.4).
    root = _root(tmp_path)
    file = root / "tests" / "a.test.js"
    message = f"Error\n    at Object.toBe ({file}:2:1)"
    report = _report(
        _suite(
            file,
            [
                _assertion("adds item", ancestors=("Case",), status="failed", messages=(message,)),
                _assertion("ADDS ITEM", ancestors=("Case",), status="passed"),
            ],
            status="failed",
        )
    )
    result = _run(tmp_path, root, report=report)

    assert len(result.warnings) == 1
    assert "tests/a.test.js::Case > adds item" in result.warnings[0]


def test_selected_name_that_matches_nothing_is_an_error_even_on_exit_zero(tmp_path: Path) -> None:
    root = _root(tmp_path)
    report = _report(
        _suite(root / "tests" / "a.test.js", [_assertion("other", ancestors=("Cart",), status="pending")])
    )
    result = _run(
        tmp_path,
        root,
        select=("tests/a.test.js::Cart > nothing here",),
        report=report,
        exit_code=0,
    )

    assert result.status is Status.ERROR
    assert result.error is not None and result.error.code is ErrorCode.NO_TESTS
    assert "did not run" in result.error.message


def test_selected_name_that_is_only_pending_is_not_proof_it_ran(tmp_path: Path) -> None:
    root = _root(tmp_path)
    report = _report(
        _suite(root / "tests" / "a.test.js", [_assertion("adds item", ancestors=("Cart",), status="pending")])
    )
    result = _run(tmp_path, root, select=("tests/a.test.js::Cart > adds item",), report=report, exit_code=0)

    assert result.error is not None and result.error.code is ErrorCode.NO_TESTS


def test_every_selected_name_must_run_not_just_one(tmp_path: Path) -> None:
    root = _root(tmp_path)
    report = _report(
        _suite(
            root / "tests" / "a.test.js",
            [
                _assertion("one", ancestors=("Cart",), status="passed"),
                _assertion("two", ancestors=("Cart",), status="pending"),
            ],
        )
    )
    result = _run(
        tmp_path,
        root,
        select=("tests/a.test.js::Cart > one", "tests/a.test.js::Cart > two"),
        report=report,
        exit_code=0,
    )

    assert result.error is not None and result.error.code is ErrorCode.NO_TESTS
    assert "Cart > two" in result.error.message


def test_selected_test_that_ran_is_reported_with_the_run_counts(tmp_path: Path) -> None:
    root = _root(tmp_path)
    report = _report(
        _suite(
            root / "tests" / "a.test.js",
            [
                _assertion("adds item", ancestors=("Cart",), status="passed"),
                _assertion("removes item", ancestors=("Cart",), status="pending"),
            ],
        )
    )
    result = _run(tmp_path, root, select=("tests/a.test.js::Cart > adds item",), report=report, exit_code=0)

    assert result.status is Status.PASSED
    assert _counts(result) == (2, 1, 0, 1, 0)


def test_coverage_request_is_not_built_for_jest_and_says_so(tmp_path: Path) -> None:
    root = _root(tmp_path)
    report = _report(_suite(root / "tests" / "a.test.js", [_assertion("x")]))
    result = _run(tmp_path, root, report=report, exit_code=0, coverage=True)

    assert result.coverage is None
    assert any("coverage" in w for w in result.warnings)
    assert _counts(result) == (1, 1, 0, 0, 0)


def test_duration_is_the_sum_of_suite_times(tmp_path: Path) -> None:
    root = _root(tmp_path)
    report = _report(
        _suite(root / "tests" / "a.test.js", [_assertion("x")], start=1000, end=1500),
        _suite(root / "tests" / "b.test.js", [_assertion("y")], start=2000, end=2250),
    )
    result = _run(tmp_path, root, report=report, exit_code=0)

    assert result.duration_ms == 750


def test_parse_finds_the_run_state_beside_the_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # api.parse gives only the report path. The run state beside it keeps names relative to the project,
    # whatever the current directory is.
    root = _root(tmp_path)
    workdir = tmp_path / "work"
    workdir.mkdir()
    JestAdapter().build_command(TestRequest(cwd=root), workdir)
    test_file = root / "tests" / "a.test.js"
    report = _report(_suite(test_file, [_assertion("x", status="failed", messages=(f"at ({test_file}:4:2)",))]))
    (workdir / "jest-report.json").write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = api.parse("jest", workdir / "jest-report.json")

    assert result.failures[0].name == "tests/a.test.js::x"
    assert result.failures[0].line == 4


def test_parse_of_a_saved_report_uses_the_current_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # No run state beside the report: names are relative to the current directory.
    root = _root(tmp_path)
    test_file = root / "tests" / "a.test.js"
    report_path = tmp_path / "saved.json"
    report = _report(
        _suite(test_file, [_assertion("x", status="failed", messages=(f"at ({test_file}:4:2)",))], status="failed")
    )
    report_path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.chdir(root)
    result = JestAdapter().parse([report_path], 1, "", False)

    assert result.failures[0].file == "tests/a.test.js"
    assert result.failures[0].line == 4


# ---------------------------------------------------------------- live runs (need jest)


def _line_of(path: Path, needle: str) -> int:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if needle in line:
            return number
    raise AssertionError(f"{needle!r} not in {path}")


def _link_jest(root: Path) -> None:
    """Link JEST_NODE_MODULES into the project, then check `npx --no-install jest` works there. Skips otherwise."""
    modules = os.environ.get(JEST_NODE_MODULES_ENV)
    if modules:
        try:
            os.symlink(Path(modules).resolve(), root / "node_modules", target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"cannot link {modules} into the test project: {exc}")
    npx = shutil.which("npx")
    if npx is None:
        pytest.skip("npx is not on PATH, so jest cannot run")
    probe = subprocess.run(
        [npx, "--no-install", "jest", "--version"],
        cwd=root,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=120,
        check=False,
    )
    if probe.returncode != 0:
        pytest.skip(
            f"jest is not installed for this project; set {JEST_NODE_MODULES_ENV} to a node_modules folder that "
            "holds jest (for example from npm install --save-dev jest@29 in a scratch folder outside the repo)"
        )


def _project(tmp_path: Path, *, fixture: Path | None = None, files: dict[str, str] | None = None) -> Path:
    root = tmp_path / "project"
    if fixture is not None:
        shutil.copytree(fixture, root)
    else:
        root.mkdir()
        (root / "package.json").write_text('{"name": "live", "private": true}\n', encoding="utf-8")
        for rel, text in (files or {}).items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    _link_jest(root)
    return root


def _live(root: Path, *, select: tuple[str, ...] = (), timeout: int = 180, kill_grace: int = 5) -> TestResult:
    return api.run(
        TestRequest(
            cwd=root,
            framework="jest",
            select=select,
            timeout_seconds=timeout,
            kill_grace_seconds=kill_grace,
        )
    )


CLASH = """describe('A B', () => {
  test('c', () => {
    expect(1).toBe(1);
  });
});
describe('A', () => {
  test('B c', () => {
    expect(2).toBe(3);
  });
});
describe('Case', () => {
  test('adds item', () => {});
  test('ADDS ITEM', () => {});
});
"""


def test_live_mixed_fixture_run_and_parse_give_identical_counts(tmp_path: Path) -> None:
    root = _project(tmp_path, fixture=FIXTURE)
    result = _live(root)

    assert result.status is Status.FAILED
    assert result.error is None
    assert _counts(result) == (5, 3, 1, 1, 0)
    assert result.raw.report_path is not None

    parsed = api.parse("jest", Path(result.raw.report_path))
    assert _counts(parsed) == _counts(result)
    assert parsed.status is result.status

    failure = result.failures[0]
    assert failure.name == "tests/mixed.test.js::Mixed > fails here"
    assert failure.file == "tests/mixed.test.js"
    assert failure.line == _line_of(root / "tests" / "mixed.test.js", "toBe(3)")
    assert [(f.name, f.file, f.line) for f in parsed.failures] == [(f.name, f.file, f.line) for f in result.failures]


def test_live_selecting_one_name_runs_only_that_test(tmp_path: Path) -> None:
    result = _live(_project(tmp_path, fixture=FIXTURE), select=("tests/mixed.test.js::Mixed > passes two",))

    assert result.status is Status.PASSED
    assert _counts(result) == (5, 1, 0, 4, 0)


def test_live_selecting_a_file_path_runs_that_file(tmp_path: Path) -> None:
    result = _live(_project(tmp_path, fixture=FIXTURE), select=("tests/mixed.test.js",))

    assert _counts(result) == (5, 3, 1, 1, 0)


def test_live_name_that_matches_no_test_is_an_error_not_a_pass(tmp_path: Path) -> None:
    result = _live(_project(tmp_path, fixture=FIXTURE), select=("tests/mixed.test.js::Mixed > no such test",))

    assert result.status is Status.ERROR
    assert result.error is not None and result.error.code is ErrorCode.NO_TESTS


def test_live_title_with_regex_characters_is_selected_by_name(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        files={
            "tests/special.test.js": (
                "describe('Cart', () => {\n"
                "  test('has [brackets] and (parens) and $dollar', () => {});\n"
                "  test('other', () => {});\n"
                "});\n"
            )
        },
    )
    result = _live(root, select=("tests/special.test.js::Cart > has [brackets] and (parens) and $dollar",))

    assert result.status is Status.PASSED
    assert _counts(result) == (2, 1, 0, 1, 0)


def test_live_name_clash_is_reported_with_the_shared_fullname(tmp_path: Path) -> None:
    root = _project(tmp_path, files={"tests/clash.test.js": CLASH})
    result = _live(root)

    assert result.status is Status.FAILED
    assert _counts(result) == (4, 3, 1, 0, 0)
    assert result.raw.report_path is not None
    report = json.loads(Path(result.raw.report_path).read_text(encoding="utf-8"))
    names = [(a["fullName"], a["status"]) for suite in report["testResults"] for a in suite["assertionResults"]]
    assert ("A B c", "passed") in names and ("A B c", "failed") in names

    failure = result.failures[0]
    assert failure.name == "tests/clash.test.js::A > B c"
    assert failure.line == _line_of(root / "tests" / "clash.test.js", "toBe(3)")
    assert [w for w in result.warnings if "tests/clash.test.js::A > B c" in w]


def test_live_selecting_a_clashing_name_also_runs_its_twin(tmp_path: Path) -> None:
    # 6.4: -t matches fullName, so selecting 'A > B c' runs both tests whose fullName is 'A B c'.
    root = _project(tmp_path, files={"tests/clash.test.js": CLASH})
    result = _live(root, select=("tests/clash.test.js::A > B c",))

    assert result.status is Status.FAILED
    assert _counts(result) == (4, 1, 1, 2, 0)


def test_live_t_pattern_is_case_insensitive(tmp_path: Path) -> None:
    # Observed in jest 29 and 30: selecting 'Case adds item' also runs 'Case ADDS ITEM'.
    root = _project(tmp_path, files={"tests/clash.test.js": CLASH})
    result = _live(root, select=("tests/clash.test.js::Case > adds item",))

    assert result.status is Status.PASSED
    assert _counts(result) == (4, 2, 0, 2, 0)


def test_live_beforeall_throw_is_failed_tests_not_a_load_failure(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        files={
            "tests/hook.test.js": (
                "describe('Hook', () => {\n"
                "  beforeAll(() => { throw new Error('beforeAll broke'); });\n"
                "  test('a', () => {});\n"
                "  test('b', () => {});\n"
                "});\n"
            )
        },
    )
    result = _live(root)

    assert result.status is Status.FAILED
    assert result.error is None
    assert _counts(result) == (2, 0, 2, 0, 0)


def test_live_afterall_throw_is_collection_not_a_green_run(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        files={
            "tests/after.test.js": (
                "describe('AA', () => {\n"
                "  afterAll(() => { throw new Error('afterAll broke'); });\n"
                "  test('p', () => { expect(1).toBe(1); });\n"
                "});\n"
            )
        },
    )
    result = _live(root)

    assert result.status is Status.ERROR
    assert result.error is not None and result.error.code is ErrorCode.COLLECTION
    assert _counts(result) == (None,) * 5


def test_live_load_failure_is_collection_error_and_not_counted(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        files={
            "tests/throws.test.js": "throw new Error('boom at load');\n",
            "tests/ok.test.js": "test('fine', () => {});\n",
        },
    )
    result = _live(root)

    assert result.status is Status.ERROR
    assert result.error is not None and result.error.code is ErrorCode.COLLECTION
    assert "boom at load" in result.error.message
    assert _counts(result) == (None,) * 5


def test_live_project_with_no_tests_is_no_tests_error(tmp_path: Path) -> None:
    root = _project(tmp_path, files={"README.txt": "no tests here\n"})
    result = _live(root)

    assert result.status is Status.ERROR
    assert result.error is not None and result.error.code is ErrorCode.NO_TESTS


def test_live_timeout_with_no_report_has_null_counts(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        files={
            "tests/slow.test.js": (
                "test('spins', () => {\n"
                "  const end = Date.now() + 60000;\n"
                "  while (Date.now() < end) {}\n"
                "});\n"
            )
        },
    )
    result = _live(root, timeout=3, kill_grace=1)

    assert result.status is Status.TIMEOUT
    assert _counts(result) == (None,) * 5


def test_live_project_without_local_jest_is_tool_missing(tmp_path: Path) -> None:
    if shutil.which("npx") is None:
        pytest.skip("npx is not on PATH")
    if shutil.which("jest") is not None:
        pytest.skip("a global jest is on PATH, so a project without jest would still find one")
    root = tmp_path / "project"
    (root / "tests").mkdir(parents=True)
    (root / "package.json").write_text('{"name": "bare", "private": true}\n', encoding="utf-8")
    (root / "tests" / "a.test.js").write_text("test('x', () => {});\n", encoding="utf-8")
    result = _live(root)

    assert result.status is Status.ERROR
    assert result.error is not None and result.error.code is ErrorCode.TOOL_MISSING
