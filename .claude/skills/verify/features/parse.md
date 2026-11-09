# Parse an existing report

## Sub-features

- `parse <framework> <file>` reads a JUnit XML report without running tests (5.1, criterion 6).
- `--json` prints the complete result.

## How to get to it (user POV)

Run `test-adapters parse pytest <junit.xml>`.

## Driving it with the CLI

Write a report with `uvx --with pytest python -m pytest -q --junitxml=<file>` in the fixture folder, then run the parse command.

Observable end state: the same counts and status as `run` on the same project. For the fixture, exit 1 and `failed 5 3 1 1 0`.

## Gotchas

- A missing or malformed report returns `error` with `unparseable_report`, exit 3.
- The report must come from pytest. Other frameworks are not built.
