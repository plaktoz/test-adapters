# test-adapters: Roadmap

> Status: Draft v0.2 · Self-contained. Requirements and acceptance criteria are in [requirements.md](./requirements.md); this file does not repeat them. It records the phasing and what each phase needs.

## Goal

An agent or CI job in any Python or JavaScript repo trusts the red/green signal it gets, acts on it without reading framework output, and never blames a code change for a tooling fault.

"Trusts" has to be shown, not assumed. That is why the first release includes validation on real projects, not only fixtures.

## Phase 1: Build to spec

Implement the pytest and jest adapters, the CLI, the exit codes and the default view as described in `requirements.md`.

- Done when: acceptance criteria 1 to 18, 24 and 25 pass.
- Before building each adapter, run the live checks listed under "Not yet verified" in requirements section 6.2 and record the results there.

## Phase 2: Prove it on real projects

Done when: acceptance criteria 19 to 21 pass on Linux and macOS with zero unexplained disagreements, and criterion 23 passes. Criterion 22 is reported as a pilot, not gated (D14, D23). Windows is implemented but not tested in v0.1.0 (D20), so it is not part of the done condition.

Order inside the phase:

1. **Corpus and agreement (19).** Choose and pin the corpus (the owner approves the list first), then compare counts and exit codes against the framework's own. Zero unexplained disagreements. This is cheap and finds spec errors early.
2. **Mutation matrix (20) and platform matrix (21).** Run in GitHub Actions on Linux and macOS. Windows has no CI job in v0.1.0 (D20). Its tests are tracked as a GitHub issue.
3. **Agent A/B pilot (22).** 3 bugs × 2 arms, plus 1 spare, 7 sessions at most, run after correctness is stable. The result is reported, not gated. A missed token target triggers a default-view tuning pass in v0.2.
4. **Adoption (23).** Packaging to PyPI and the instruction snippet. One fresh-session check, outside the pilot cap, after owner approval. Without this, the agent benefit never happens, however good the view is.

## Phase 3: Keep the signal trustworthy over time

Not part of the first release. Each item needs its own requirements section before work starts.

- **Run history.** A local file (for example `.test-adapters/history.jsonl`) records each run. `flaky` becomes a per-test flake rate across runs, not a single-run observation. This needs `schema_version: 2` for the derived fields.
- **Changed-file selection.** `run --changed <git-ref>` selects the tests a diff can affect, using history and coverage. This moves "impact analysis" out of the non-goals, which is an explicit decision for the owner.
- **Canary.** The corpus job runs weekly against the newest pytest and jest releases, so a framework change that breaks parsing is caught before users hit it.
- **More frameworks.** vitest, `go test` or cargo, chosen by demand. Each needs fixtures and a report-source check (requirements section 11).

## What the owner must provide or decide

| Item | Needed for | Decision |
|------|------------|----------|
| GitHub Actions CI in `plaktoz/test-adapters`, Linux and macOS runners | Phase 2 (19 to 21) | Decided (D22) |
| The corpus list (20 repos, 12 pytest and 8 jest, pinned SHAs) | Phase 2 (19 to 21) | Approve the proposal before anything is cloned |
| Agent A/B pilot: 7 sessions, Claude Code headless, one pinned model | Phase 2 (22) | Approved |
| Adoption check: 1 session, outside the pilot cap | Phase 2 (23) | Approve before it runs |
| PyPI upload of `test-adapters` 0.1.0 | Phase 2 (23) | Approve the version and README before upload |
| Whether impact analysis becomes in scope | Phase 3 | Decide when Phase 2 is done |

## Task state

Task-level state (open, done, not done, with evidence) is kept in a separate task file once the owner approves this roadmap. This file stays the plan.
