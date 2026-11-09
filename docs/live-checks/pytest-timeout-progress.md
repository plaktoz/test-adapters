# pytest progress output after a timeout (live check)

Task T5 (issue #23). This check records what pytest writes to stdout when a run is killed, so the adapter can count tests without a JUnit report. T19 moves the result into requirements 6.2.

## Setup

- pytest: 9.2.0, Python 3.13.0, macOS. Run through `uvx --with pytest`.
- Fixture: `tests/fixtures/pytest_hang_progress/`. Two tests pass, one is skipped, one fails, and `test_hangs` sleeps 600 seconds.
- Method: run the command in the fixture directory and stop it after 6 seconds with `timeout 6`. Save stdout.

## Flag choice

- `-q -v` together: the two flags cancel. Output is the dot form `..sF`, with no test names. The adapter cannot count by name or name the running test.
- `-v` alone: one line per finished test. This is the choice.
- The adapter uses `-v` on every run, not only after a timeout. A run does not know in advance that it will time out. The `-q` flag was removed from the command.

## Excerpt, `-v`, killed during `test_hangs`

```text
collecting ... collected 5 items

tests/test_progress.py::test_pass_one PASSED                             [ 20%]
tests/test_progress.py::test_pass_two PASSED                             [ 40%]
tests/test_progress.py::test_skipped SKIPPED (skipped on purpose)        [ 60%]
tests/test_progress.py::test_fails FAILED                                [ 80%]
tests/test_progress.py::test_hangs 
```

- A finished test prints `path::name STATUS`, then an optional reason in parentheses, then a percent.
- The running test is the last line. It has no status and no final newline. This is how the adapter names the hanging test.
- The run leaves no JUnit report, so these lines are the only source of counts.

## Other cases seen

Output of a second fixture, killed during `test_last`:

```text
tests/test_p.py::test_param[a b] PASSED                                  [ 20%]
tests/test_p.py::test_param[c] PASSED                                    [ 40%]
tests/test_p.py::test_xf XFAIL (x)                                       [ 60%]
tests/test_p.py::test_err PASSED                                         [ 80%]
tests/test_p.py::test_err ERROR                                          [ 80%]
tests/test_p.py::test_last 
```

- An id can contain spaces, as in `test_param[a b]`. The parser cannot split on the first space.
- `XFAIL` prints for an expected failure. The adapter counts it as skipped, as in requirements 4.2.
- A test with a teardown error prints twice, `PASSED` and then `ERROR`, with the same id. The adapter keeps the worst outcome per id, so the test counts once. This avoids the double count in issue #42, for this path only.

## What is not verified

- Other pytest versions. Only 9.2.0 was run.
- Output with `pytest-xdist` (`-n`). Workers print lines in a different form. Not run.
- Windows. Not run (issue #11).
- Output that the project's own `pytest.ini` changes, such as `addopts = -q`. Not run.
