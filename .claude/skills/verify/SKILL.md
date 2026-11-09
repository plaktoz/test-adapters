---
name: verify
description: Drive the test-adapters CLI on the pytest fixture the way a user does, and capture evidence. Use it to prove that run, detect, parse and the usage path work end to end, or after changing the CLI, a view, or an adapter.
---

# verify: test-adapters CLI

This skill drives the real `test-adapters` command. The surface is a command-line tool, not a web app. Each drive starts a new subprocess, reads its output, and records the exit code. The fixture project is `tests/fixtures/pytest_mixed/` (3 pass, 1 fail, 1 skip; the failure is `tests/test_mixed.py::test_fails` at line 17).

## Launch

There is no server to keep alive. Launch means setting the interpreter path once:

1. Run from the repo root: `export PYTHONPATH="$PWD/src"`.
2. Use `uvx --with pytest python` as the interpreter. It provides pytest to the CLI. The CLI runs pytest with `sys.executable`, so the same interpreter must have pytest.

Ready means: `uvx --with pytest python -m test_adapters.cli doctor` prints a `framework: pytest available` line. Teardown is nothing: each drive is one short process.

## Doctor

Run this first when anything looks off. It runs no test.

```
cd tests/fixtures/pytest_mixed
PYTHONPATH="$REPO/src" uvx --with pytest python -m test_adapters.cli
```

Expect `framework: pytest available, detected` and `detected: pytest`, exit 0. If pytest is missing, the output says `missing`. Install it through `uvx --with pytest`, do not install a global copy.

## Drive

Run each drive from the fixture folder, with the same `PYTHONPATH` and interpreter as Doctor. Use `$EV` for the evidence folder (see Evidence).

1. Default view: `... -m test_adapters.cli run > $EV/run-default.txt; echo $? > $EV/run-default.exit`. Expect exit 1, `status: failed`, `summary: 3 passed, 1 failed, 1 skipped of 5`, and `tests/test_mixed.py,17,`.
2. Complete JSON: `... -m test_adapters.cli run --json --result-file $EV/result.json > $EV/run-json.txt`. Expect exit 1, and `result.json` with `total` 5 and `failures[0].line` 17.
3. Parse an existing report: write the JUnit file with `uvx --with pytest python -m pytest -q --junitxml=$EV/junit.xml`, then `... -m test_adapters.cli parse pytest $EV/junit.xml --json`. Expect exit 1 and the same counts as step 2.
4. No-argument mode: `... -m test_adapters.cli`. Expect exit 0, `detected: pytest`, and no `summary:` line (no test ran).
5. Usage error: `... -m test_adapters.cli run --no-such-flag`. Expect exit 2, and stderr that lists `valid run flags:`.
6. Refused flag: `... -m test_adapters.cli run --fields name`. Expect exit 2 and `not implemented in this release`.
7. Combined run: `... -m test_adapters.cli run --framework all`. The fixture has no `package.json`, so jest is not detected and the combined run is pytest only. Expect a first line `status: failed`, a `== pytest` block, and exit 1. A project that has jest files would add a `== jest` block with `status: error` (jest is not implemented, Phase 6), and then the overall status is `error` with exit 3.

The automated version of these drives is `tests/test_walking_skeleton.py`. Run it with `uvx --with pytest pytest -q tests/test_walking_skeleton.py`.

## Evidence

Evidence goes to `.claude/skills/verify/evidence/<UTC timestamp>/`. Create the folder before the first drive. Every drive writes its stdout and exit code there. The JSON result and the JUnit report go there too.

Proof standards:

- Run the real CLI in a subprocess. Do not call internal functions to get a result.
- Capture the action and the result state: the command, the exit code, and the output.
- Verify the side effects too: the result file exists and parses, and the JUnit file exists.
- The fixture is the only project driven. Do not use mocks.

## Cleanup

Cleanup removes scratch state only. It never removes evidence.

1. Remove the `build/` and `dist/` folders the build step made, if any.
2. Remove `/tmp/ta-*` files this skill created.
3. Keep `.claude/skills/verify/evidence/`.

Do not kill by process name. Each drive exits on its own; there is no process to kill.

## Helpers

None. The drives are plain shell commands in this file.

## Known gaps in this drive

- Windows is not driven. Issue #11 tracks it. The Windows kill path is a stub.
- The timeout path is not driven here. The timeout probe is run by hand; see README section 7.
- jest is not driven. It is not implemented (Phase 6).
