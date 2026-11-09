# Exit codes are a public contract: 0 passed, 1 failed, 2 usage, 3 error, 4 timeout

CI wrappers and merge queues branch on the exit code alone. We separate a test failure (1) from a tooling fault (3) and a timeout (4) so a caller can blame a change only for a real regression. Collapsing them would send a missing framework or a collection error to the same branch as a broken test. Any change to these codes breaks every caller, so they are fixed.
