# test-adapters: Roadmap

> Status: Draft v0.1 · Self-contained. Requirements and acceptance criteria are in [requirements.md](./requirements.md); this file does not repeat them. It records the phasing and what each phase needs.

## Goal

An agent or CI job in any Python or JavaScript repo trusts the red/green signal it gets, acts on it without reading framework output, and never blames a code change for a tooling fault.

"Trusts" has to be shown, not assumed. That is why the first release includes validation on real projects, not only fixtures.

## Phase 1: Build to spec

Implement the pytest and jest adapters, the CLI, the exit codes and the default view as described in `requirements.md`.

- Done when: acceptance criteria 1 to 18 pass.
- Before building each adapter, run the live checks listed under "Not yet verified" in requirements section 6.2 and record the results there.

## Phase 2: Prove it on real projects

Done when: acceptance criteria 19 to 23 pass.

Order inside the phase:

1. **Corpus and agreement (19).** Choose and pin the corpus, then compare counts and exit codes against the framework's own. This is cheap and finds spec errors early.
2. **Mutation matrix (20) and platform matrix (21).** Run in CI on three operating systems. The Windows process-tree kill is the most likely thing to fail.
3. **Agent A/B (22).** Costs agent sessions, so it runs after correctness is stable. If the default view loses to raw output, change the view and rerun before release.
4. **Adoption (23).** Packaging and the instruction snippet. Without this, the agent benefit never happens, however good the view is.

## Phase 3: Keep the signal trustworthy over time

Not part of the first release. Each item needs its own requirements section before work starts.

- **Run history.** A local file (for example `.test-adapters/history.jsonl`) records each run. `flaky` becomes a per-test flake rate across runs, not a single-run observation. This needs `schema_version: 2` for the derived fields.
- **Changed-file selection.** `run --changed <git-ref>` selects the tests a diff can affect, using history and coverage. This moves "impact analysis" out of the non-goals, which is an explicit decision for the owner.
- **Canary.** The corpus job runs weekly against the newest pytest and jest releases, so a framework change that breaks parsing is caught before users hit it.
- **More frameworks.** vitest, `go test` or cargo, chosen by demand. Each needs fixtures and a report-source check (requirements section 11).

## What the owner must provide or decide

| Item | Needed for | Decision |
|------|------------|----------|
| A remote repository with CI enabled, Linux, macOS and Windows runners, and network access | Phase 2 (19 to 21) | Create it and approve pushing |
| The corpus list (20 repos, pinned SHAs) | Phase 2 (19 to 21) | Approve a proposed list, or supply one |
| Agent harness and budget (about 60 sessions) | Phase 2 (22) | Grant the spend; choose the harness |
| Whether the A/B is a release gate | Phase 2 (22) | Default is yes (D14) |
| Whether impact analysis becomes in scope | Phase 3 | Decide when Phase 2 is done |

## Task state

Task-level state (open, done, not done, with evidence) is kept in a separate task file once the owner approves this roadmap. This file stays the plan.
