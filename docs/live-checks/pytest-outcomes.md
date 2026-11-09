# pytest outcomes in JUnit XML (live check)

Task T1 (issue #19). This check runs before the adapter change. It records how pytest writes four outcomes to the JUnit report, so the mapping in requirements 4.2 can be checked against real output. T19 moves the result into requirements 6.2.

## Setup

- pytest: 9.2.0, run through `uvx --with pytest pytest`.
- Fixture: `tests/fixtures/pytest_outcomes/tests/test_outcomes.py`, with one test per case.
- Command: `pytest -q --junitxml=<file>` run inside the fixture directory.
- Result: 5 testcases. Exit code 1. Summary line: `1 failed, 2 passed, 1 xfailed, 1 xpassed, 1 error`.

## Excerpts from the JUnit XML

Trimmed. The `<testsuite>` attributes are `tests="5" failures="1" errors="1" skipped="1"`.

### xfail (expected failure occurred) -> `skipped`

```xml
<testcase classname="tests.test_outcomes" name="test_xfail_expected_failure" time="0.000">
  <skipped type="pytest.xfail" message="known bug" />
</testcase>
```

### xpass, non-strict -> `passed`

```xml
<testcase classname="tests.test_outcomes" name="test_xpass_non_strict" time="0.000" />
```

The element has no child. The adapter sees it as a plain pass.

### xpass, strict -> `failed`

```xml
<testcase classname="tests.test_outcomes" name="test_xpass_strict" time="0.000">
  <failure message="[XPASS(strict)] fixed but not removed">[XPASS(strict)] fixed but not removed</failure>
</testcase>
```

### Fixture teardown error -> `errors`

The test body passes. Only the fixture teardown raises. pytest writes an `<error>` element on the testcase, and the `classname` is not empty.

```xml
<testcase classname="tests.test_outcomes" name="test_teardown_error" time="0.000">
  <error message="failed on teardown with &quot;RuntimeError: teardown broke&quot;">@pytest.fixture
def broken_teardown():
    yield "value"
&gt;       raise RuntimeError("teardown broke")
E       RuntimeError: teardown broke

tests/fixtures/pytest_outcomes/tests/test_outcomes.py:29: RuntimeError</error>
</testcase>
```

## Counts for the fixture

| Counted as | Testcases |
|------------|-----------|
| passed | `test_plain_pass`, `test_xpass_non_strict` |
| failed | `test_xpass_strict` |
| skipped | `test_xfail_expected_failure` |
| errors | `test_teardown_error` |

Total 5 = 2 + 1 + 1 + 1. The adapter counts match this table (see `tests/test_pytest_outcomes.py`).

A second fixture, `tests/fixtures/pytest_outcomes/teardown_only/`, has one passing body and one erroring teardown. It gives `total 1, errors 1, status failed`.

## Finding: a body failure and a teardown error write two testcases

A probe outside the repo ran one test whose body fails (`assert False`) and whose fixture teardown raises. pytest wrote two `<testcase>` elements with the same `classname` and `name`: one with a `<failure>` child and one with an `<error>` child. The adapter counts each element, so one test is counted twice (`failed 1, errors 1, total 2`).

Requirements 4.2 say each test is counted once, by its final outcome. This case is not in the T1 fixture, so the parser does not handle it yet. The fix belongs to a later task.

## Verification

- `uvx --with pytest pytest -q tests/test_pytest_outcomes.py`: output is recorded in the T1 task state in the issue.
