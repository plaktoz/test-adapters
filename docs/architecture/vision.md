# test-adapters: Vision

Status: APPROVED by the owner. The `unslop` prose pass (playbook Phase 0 step 4) is pending; it needs the owner to run `/unslop` themselves. Source of detail: [requirements.md](../requirements.md) v0.5 and [roadmap.md](../roadmap.md) v0.2.

## Goal

One command runs a Python or JavaScript project's tests with pytest or jest, and returns one normalised result. An agent or CI job trusts the red/green signal, acts on it without reading framework output, and never blames a code change for a tooling fault.

## Users and main flows

| # | Flow | Actor | Steps |
|---|------|-------|-------|
| 1 | CI or merge-queue gate | CI wrapper | Runs `test-adapters run --json --result-file <path>`. Decides from the exit code (0 passed, 1 failed, 3 error, 4 timeout). Reads the result file only if it needs detail. |
| 2 | Fix loop | Coding agent | Runs `test-adapters run --select <files>`. Reads the default text view. Reruns the failing tests from the `help` line. |
| 3 | Session start | Coding agent | Runs `test-adapters` with no arguments. Sees the detected framework and `doctor` status. No test is run (D8). |

The Python API used by metrics tools (`run()`, `parse()`) is a supporting interface, not a main flow.

## Current state

Greenfield. `git log` has no code, only the docs and config described in [requirements.md](../requirements.md). Nothing is implemented yet.

## Constraints

- **Language and runtime:** Python 3.11 or later. Standard library only at runtime (D16, D17).
- **Config:** `test-adapters.toml` in the working directory. No `pyproject.toml` fallback (D18).
- **Frameworks:** pytest and jest only in v0.1.0. Others are deferred (roadmap Phase 3).
- **Platforms:** Windows is implemented in v0.1.0 (D20). Linux and macOS are tested in CI. Windows has no test job in v0.1.0.
- **Packaging and license:** MIT. PyPI `test-adapters` 0.1.0, installed with `pipx` or `uv tool`. Upload needs owner approval (D19).
- **CI:** GitHub Actions in `plaktoz/test-adapters` (D22).
- **Off-limits:** nothing beyond the non-goals in requirements §2. The library does not check out branches, generate tests, enforce TDD, or do impact analysis.
- **Deadline:** none. Phases end on exit checks, not on dates.
- **Spend:** the agent A/B pilot is capped at 7 Claude Code headless sessions, one pinned model. One adoption session runs outside that cap after approval (D23, criteria 22 and 23).

## Done condition for v0.1.0 (pass/fail)

The release is done when every item below passes, with the evidence named:

1. **Spec tests:** acceptance criteria 1–18, 24 and 25 pass in CI on Linux and macOS. Evidence: CI run link.
2. **Agreement:** criterion 19 on the pinned corpus gives zero unexplained disagreements with the frameworks' own counts. Each documented exception has a fixture and a `docs/` entry. Evidence: agreement report.
3. **Mutation and platform matrix:** criteria 20 and 21 pass on Linux and macOS, on Python 3.11 and the latest release, and on pytest 8 and 9 and jest 29 and 30. Evidence: matrix results.
4. **Adoption:** criterion 23 passes. A fresh headless session given only the snippet runs `test-adapters run` on its first test run. Evidence: session transcript.
5. **A/B pilot reported:** criterion 22 is recorded (3 bugs × 2 arms, plus 1 spare, at most 7 sessions). Token and turn counts are reported. Fix rate is marked "not measured". The result does not gate the release (D14).
6. **Windows** is documented as "implemented, not tested on Windows". No claim of support or verification is made (D20). Its testing is tracked as an open issue.

Not part of the done condition: Windows testing, the 30-bug A/B, run history, changed-file selection, the weekly canary, and new frameworks (roadmap Phase 3).

## Stop conditions

Stop and ask the owner if:

- The corpus proposal is not approved, or a repo cannot be pinned.
- A disagreement with a framework cannot be explained by a fixture.
- The pilot approaches the 7-session cap before the arms are complete.
- A step needs an external action: pushing a tag, uploading to PyPI, or spending beyond the caps.
