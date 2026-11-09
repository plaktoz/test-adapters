# Run tests and read the result

## Sub-features

- Default text view (5.5): `status:`, `summary:`, `failures[n of N]`, `flaky:`, `help:`.
- JSON view: `run --json`, and `--result-file <path>` for the complete result.
- Exit codes: 0 passed, 1 failed, 3 error, 4 timeout, 2 usage (5.4).

## How to get to it (user POV)

Run `test-adapters run` in a project folder, or pass `--cwd <dir>`.

## Driving it with the CLI

From the fixture folder `tests/fixtures/pytest_mixed`, with `PYTHONPATH` set to `src` and an interpreter that has pytest:

`uvx --with pytest python -m test_adapters.cli run` gives exit 1 and `summary: 3 passed, 1 failed, 1 skipped of 5`.

Observable end state: `failures[1 of 1]` names `tests/test_mixed.py::test_fails` at line 17.

## Gotchas

- `--coverage`, `--retry-failed`, `--retry-mode isolated` and `--fields` exit 2. They are not built.
- `--framework all` with jest files gives an error entry for jest, because jest is not built.
- A timed-out run returns `timeout` with counts `null`. The grace period adds about 5 seconds.
