# Detect frameworks and check the tool

## Sub-features

- No-argument mode: lists detected frameworks and their availability. It runs no test (5.3, D8).
- `doctor`: reports whether each framework's requirement is installed.

## How to get to it (user POV)

Run `test-adapters` with no arguments, or `test-adapters doctor`.

## Driving it with the CLI

From the fixture folder: `uvx --with pytest python -m test_adapters.cli` gives exit 0, `detected: pytest`, and no `summary:` line.

Observable end state: no test ran, so no junit report or summary appears.

## Gotchas

- An empty folder returns `detected: none` and exit 0. This is correct, not a failure.
- `doctor` checks presence only. It does not check versions.
