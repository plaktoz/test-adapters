# v0.1.0 task list

Phase 5 breakdown of the remaining work in `docs/requirements.md` (v0.5). Each task is a GitHub issue with the task card: goal, files allowed and off-limits, contracts, acceptance checks, verify command, and evidence needed. The issue is the card. This file records order, blockers, state and the reason for each blocker.

Labels: `ready-for-agent` means an AFK task, with no owner input needed. `ready-for-human` means the task needs an owner decision or an external action before it can start.

Approval: the owner gave blanket approval for Phase 5 task cards as issues labelled `ready-for-agent`. Owner approval is still needed before each HITL task starts (see the Stop column in the table).

## State key

- `[ ]` open
- `[x]` done, with the PR and how it was verified
- `[-]` not done, with the reason

## Tasks

| Task | Issue | Label | Blocked by | Why it waits | Files that conflict | State |
|------|-------|-------|------------|--------------|---------------------|-------|
| T1 pytest outcome mapping (xfail, xpass, fixture errors) | #19 | ready-for-agent | none | Starts the pytest line. Edits `pytest_adapter.py` | `pytest_adapter.py` (T2, T5, T9) | [x] PR #43. Verified live on pytest 9.2.0 and by `./scripts/check` (exit 0). Found a double count (body failure plus teardown error), filed as #42 |
| T2 pytest coverage | #20 | ready-for-agent | T1 | Both edit `pytest_adapter.py` | `pytest_adapter.py` | [x] PR #47. `./scripts/check` exit 0. The pytest-cov cases ran in the worker's run; 3 tests skip on a machine without pytest-cov |
| T3 pytest retries | #21 | ready-for-agent | T1 | Flaky counts depend on the outcome mapping | `api.py` | [x] PR #48. `./scripts/check` exit 0. Live: a flaky test gives passed with 2 attempts; file and isolated modes rerun a,b,a,b and a,b,b |
| T4 `select` with `framework: all` | #22 | ready-for-agent | T3 | Both edit `api.py` | `api.py` | [x] PR #49. `./scripts/check` exit 0. The new tests failed before the change. CLI exit 3 checked |
| T5 pytest timeout counts from stdout | #23 | ready-for-agent | T9 | Both edit `pytest_adapter.py`, so run in order | `pytest_adapter.py` | [ ] |
| T6 timeout kills child processes (POSIX) | #24 | ready-for-agent | none | Tests only. No shared file with a parallel task | none | [x] PR #45. A mutation check showed the test fails without the group kill. POSIX only; skipped on Windows |
| T7 config file `test-adapters.toml` | #25 | ready-for-agent | none | Edits `config.py` and `cli.py`. Runs in round 1 | `cli.py` (T12, T20) | [x] PR #44. `./scripts/check` exit 0. Precedence: flag, environment, file, default. Env var names `TEST_ADAPTERS_<KEY>` await owner confirmation |
| T8 collection and no-tests errors | #26 | ready-for-agent | none | Tests only. The behaviour already exists | none | [x] PR #40. `./scripts/check` exit 0 |
| T9 pytest parallelism | #27 | ready-for-agent | T2 | Both edit `build_command` in `pytest_adapter.py` | `pytest_adapter.py` | [x] PR #50. `./scripts/check` exit 0. A real run with xdist used `-n 2` and returned 3 passed, 1 failed, 1 skipped |
| T10 Windows kill path | #28 | ready-for-agent | none | Edits `execution.py`. Verified by reading only | `execution.py` | [x] PR #41. Verified by reading only. Not run on Windows (issue #11) |
| T11 live jest facts | #29 | ready-for-human | owner approves the jest install | The jest install is a dependency install, which needs approval | `docs/live-checks/jest.md` | [ ] |
| T12 `--fields` and the default view rules | #30 | ready-for-agent | T7 | Both edit `cli.py` | `cli.py`, `render.py` | [ ] PR #51 open. Owner dropped the `--fields duration` item (issue #30) |
| T13 jest run and parse | #31 | ready-for-agent | T11 | The live facts decide the parse rules | `jest_adapter.py` | [ ] |
| T14 jest retries | #32 | ready-for-agent | T13, T3 | Edits `jest_adapter.py` after T13. Uses the retry loop from T3 | `jest_adapter.py` | [ ] |
| T15 jest coverage | #33 | ready-for-agent | T14 | Edits `jest_adapter.py` after T14 | `jest_adapter.py` | [ ] |
| T16 corpus agreement and mutation matrix | #34 | ready-for-human | T13, T14, T15; owner approves the corpus and the CI clone | The corpus needs jest, and the clone is a stop condition | `.github/workflows/ci.yml` | [ ] |
| T17 agent A/B pilot | #35 | ready-for-human | T16; owner approves 7 sessions; the gateway fixes the model, so the pilot records it | The pilot needs the corpus result first, and spend needs approval | `docs/ab-pilot.md` | [ ] |
| T18 adoption and PyPI | #36 | ready-for-human | T12, T13, T16, T17, T20; owner approves the session and the upload | Both need owner approval. Both are stop conditions | `docs/adoption.md`, `pyproject.toml` | [ ] |
| T19 integration | #37 | ready-for-agent | T1 to T10, T12 to T15, T20 | The full flow runs on the merged result | `docs/tasks.md`, `docs/requirements.md` (6.2 only), `docs/live-checks/` | [ ] |
| T20 remove the four refusals, update the README | #38 | ready-for-agent | T2, T3, T7, T9, T12, T14, T15 | Only this card edits the `cli.py` refusals and the README | `cli.py` (refusal block), `README.md` | [ ] |

## Parallel rounds

Tasks in one round have no blockers between them, and their files do not overlap. Only AFK tasks run in parallel (playbook Phase 6).

- **Round 1 (no blockers):** T1, T6, T7, T8, T10. Files: `pytest_adapter.py`; tests only; `config.py` and `cli.py`; tests only; `execution.py`. No overlap.
- **Round 2 (after T1 and T7):** T2, T3, T12 (T12 waits for T7). Files: `pytest_adapter.py`; `api.py`; `render.py` and `cli.py`. No overlap.
- **Round 3:** T4 (after T3), T9 (after T2), T5 (after T9), T20 (after T2, T3, T7, T9, T12, T14, T15).
- **jest chain:** T11 (owner approval), then T13, T14, T15. All edit `jest_adapter.py`, so they run in order.
- **Owner-gated chain:** T16, T17, T18. Each needs owner approval before it starts.
- **Last:** T19, after every AFK change.

## Phase 5 exit check

- [x] Every task has acceptance checks, an allowed-files list, and blockers. (Each issue body lists them.)
- [x] No two tasks that can run in parallel share allowed files. Checked by hand against the rounds above.
- [ ] The owner approves the breakdown. Blanket approval covers the issues. The owner should confirm that the HITL tasks (T11, T16, T17, T18) stay on hold until approved.

## Notes

- Issue #11 (Windows testing) stays open with label `ready-for-human`. T10 writes the Windows code, but T10 does not test Windows.
- The README line for each feature changes only in T20, so no other card edits the README. T19 checks the README against the code at the end.
- The live-check results for pytest (T1, T5) and jest (T11) go to `docs/live-checks/` first. T19 moves them into requirements 6.2.
