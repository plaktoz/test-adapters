# jest JSON report (live check)

Task T11 (issue #29). This check runs before the jest adapter is built. It records what `jest --json --outputFile` writes for jest 29 and jest 30, so the open jest bullets in requirements 6.2 can be answered from real output. T19 moves the result into requirements 6.2.

## Setup

- jest 29: `29.7.0`, from `npx jest --version`, installed with `npm install --save-dev jest@29` in `/tmp/ta-jest-29`.
- jest 30: `30.5.2`, from `npx jest --version`, installed with `npm install --save-dev jest@30` in `/tmp/ta-jest-30`.
- Node v26.13.0, npm 11.20.0, macOS 27.2.1. The owner approved both installs for this task only. Both folders are outside the repo. Nothing was installed globally, and the repo has no `package.json` or `node_modules`.
- Each scratch folder has its own `npm init -y`, no jest config, and the sample files in `tests/`. Both versions use the default runner, jest-circus (`jest-circus` has the same version as jest).
- The same eight sample files ran on both versions. The results below are the same for both versions unless a section says otherwise.

## Sample files

`tests/cart.test.js` is the main file. The line numbers are the real ones, because the line check depends on them.

```js
 1  describe('Cart', () => {
 2    test('adds item', () => {
 3      expect(1 + 1).toBe(2);
 4    });
 5
 6    test('removes item', () => {
 7      expect(1 + 1).toBe(3);
 8    });
 9
10    test.skip('skipped by test.skip', () => {});
11
12    test.todo('todo item');
13
14    xit('skipped by xit', () => {});
15
16    describe('nested', () => {
17      it('works in nested describe', () => {
18        expect(true).toBe(true);
19      });
20    });
21
22    describe.skip('skipped group', () => {
23      it('inside skipped describe', () => {});
24    });
25
26    xdescribe('xdescribe group', () => {
27      it('inside xdescribe', () => {});
28    });
29
30    test.each([[1], [2]])('each case %i', (n) => {
31      expect(n).toBeGreaterThan(0);
32    });
33
34    test('has [brackets] and (parens) and $dollar', () => {});
35  });
36
37  test('top level test', () => {});
```

The other files:

| File | Content |
|------|---------|
| `only.test.js` | `describe('Only')` with `test.only('the only one')`, `test('not run because of only')` and `test.todo('todo next to only')` |
| `allskip.test.js` | `describe('AllSkipped')` with `test.skip('one')` and `test.todo('two')` |
| `dup.test.js` | `describe('Dup')` with two tests titled `same title`. The first passes and the second fails |
| `hook.test.js` | `describe('Hook')` with a `beforeAll` that throws `beforeAll broke`, and tests `a` and `b` |
| `syntax.test.js` | `expect(1 +).toBe(2);` inside a test (a syntax error) |
| `missing.test.js` | `require('./does-not-exist');` at the top level |
| `throws.test.js` | `throw new Error('boom at load');` at the top level |
| `empty.test.js` | `describe('Empty', () => {});` with no test |

## Commands

Run inside `/tmp/ta-jest-29` and `/tmp/ta-jest-30`. `$F` is one of the sample names above.

```text
npx jest --version
npx jest --json --outputFile=out/$F.json --runTestsByPath tests/$F.test.js
npx jest --json --testLocationInResults --outputFile=out/$F.loc.json --runTestsByPath tests/$F.test.js
npx jest --json --outputFile=out/stab1.json          # whole folder, run 3 times (stab1 to stab3)
npx jest --json --maxWorkers=1 --outputFile=out/stab_w1.json
npx jest --json --outputFile=out/sel.json --runTestsByPath tests/cart.test.js -t '^Cart adds item$'
npx jest --json tests/empty.test.js                  # JSON on stdout, no --outputFile
```

Exit codes seen with `--runTestsByPath`, the same on both versions: `cart` 1, `only` 0, `allskip` 0, `dup` 1, `syntax` 1, `missing` 1, `throws` 1, `hook` 1, `empty` 1, whole folder 1.

With `--outputFile`, stdout is empty (0 bytes). Jest writes its human-readable report to stderr. Without `--outputFile`, `--json` writes the JSON object to stdout.

## JSON shape

The top-level keys are the same on both versions:

```text
numFailedTestSuites, numFailedTests, numPassedTestSuites, numPassedTests,
numPendingTestSuites, numPendingTests, numRuntimeErrorTestSuites, numTodoTests,
numTotalTestSuites, numTotalTests, openHandles, snapshot, startTime, success,
testResults, wasInterrupted
```

Counts for `cart.test.js`, from `cart.json` (both versions):

```json
{ "numTotalTests": 12, "numPassedTests": 6, "numFailedTests": 1,
  "numPendingTests": 4, "numTodoTests": 1,
  "numFailedTestSuites": 1, "numRuntimeErrorTestSuites": 0, "success": false }
```

- `numPendingTests` counts only the tests with status `pending` (4 here: `test.skip`, `xit`, and the two tests in skipped groups). `numTodoTests` counts the `todo` tests. The total is `6 + 1 + 4 + 1 = 12`.
- `testResults` has one entry per test file. Its keys are `assertionResults`, `endTime`, `message`, `name`, `startTime`, `status`, `summary`. `name` is the absolute path of the test file (here `/private/tmp/ta-jest-29/tests/cart.test.js`). The adapter must make it relative to `cwd`.
- `assertionResults` has one entry per test. Keys in jest 29: `ancestorTitles, duration, failureDetails, failureMessages, fullName, invocations, location, numPassingAsserts, retryReasons, status, title`. Jest 30 adds `failing, retryMessages, startAt`.
- The order of `testResults` is not stable. With several files and workers, the order differed between the two versions and between runs. The adapter must not depend on it.

A passing test, jest 29, with `--testLocationInResults` (jest 30 is the same plus `failing`, `retryMessages` and `startAt`):

```json
{
  "ancestorTitles": ["Cart"],
  "duration": 1,
  "failureDetails": [],
  "failureMessages": [],
  "fullName": "Cart adds item",
  "invocations": 1,
  "location": { "column": 3, "line": 2 },
  "numPassingAsserts": 1,
  "retryReasons": [],
  "status": "passed",
  "title": "adds item"
}
```

## Bullet 1: file and line information

Observed on both versions.

- `testResults[].name` gives the file. It is an absolute path.
- Without `--testLocationInResults`, every `assertionResults[].location` is `null`.
- With `--testLocationInResults`, `location` is `{ "column": N, "line": N }`. It is the position where the test is defined, not where the assertion failed:

  | Test | `location` | Note |
  |------|------------|------|
  | `adds item` | `{"column": 3, "line": 2}` | `test(` at line 2 |
  | `removes item` | `{"column": 3, "line": 6}` | The failing assertion is on line 7 |
  | `skipped by test.skip` | `{"column": 8, "line": 10}` | Column 8 is the `.skip`, not the start of the call |
  | `todo item` | `{"column": 8, "line": 12}` | The same, for `.todo` |
  | `each case 1` and `each case 2` | `{"column": 24, "line": 30}` | Both cases share one location |

- The line of a failure is not a field. It is in the stack text of `failureMessages[]`, as a frame with an absolute path:

  ```text
  at Object.toBe (/private/tmp/ta-jest-29/tests/cart.test.js:7:19)
  ```

  Jest 30 gives the same frame with its own path. The first `at` frame is the failure line for an assertion (`cart.test.js:7:19`) and for a throwing hook (`hook.test.js:3:11`). `failureDetails[]` has `matcherResult` for an assertion failure and is an empty object for a thrown error. It has no line.
- `suite.message` holds the full formatted failure text with a code frame, for example `> 7 |     expect(1 + 1).toBe(3);`.

Finding for the adapter: the failure `line` comes from the first `at <path>:<line>:<col>` frame in `failureMessages[0]`. `--testLocationInResults` is not needed for that. It is needed only if the adapter wants the definition line of a test (for example for a skipped test). It does not change the other fields.

## Bullet 2: statuses

Observed on both versions.

| Source | `assertionResults[].status` | Counted by jest in |
|--------|-----------------------------|--------------------|
| `test.skip`, `xit`, a test inside `describe.skip` or `xdescribe` | `pending` | `numPendingTests` |
| `test.todo` | `todo` | `numTodoTests` |
| A test that did not match `-t` | `pending` | `numPendingTests` |
| A test next to `test.only` that did not run | `pending` | `numPendingTests` |
| A test that ran and passed | `passed` | `numPassedTests` |
| A test that ran and failed | `failed` | `numFailedTests` |
| `skipped` | not seen on a test | |
| `disabled` | not seen on a test | |

Excerpts, jest 29 (`location` filled by `--testLocationInResults`):

```json
{ "fullName": "Cart skipped by test.skip", "status": "pending", "duration": null,
  "location": { "column": 8, "line": 10 } }
{ "fullName": "Cart todo item", "status": "todo", "duration": null,
  "location": { "column": 8, "line": 12 } }
```

- A skipped or todo test has `duration: null`, an empty `failureMessages` and `numPassingAsserts: 0`.
- `skipped` and `disabled` never appeared on a test. The `Status` type in `@jest/types` lists them (`passed, failed, skipped, pending, todo, disabled, focused`), but a search of `jest-circus`, `@jest/*` and `jest-runner` in both installs found `'disabled'` only in that type file. The adapter should accept `skipped` and `disabled` as skip-like, and it should treat them as unconfirmed until a run shows them.
- A `-t` pattern that matches no test does not fail. `-t '^No such test$'` on `cart.test.js` gave `numPendingTests: 12`, `success: true` and exit 0. The adapter must not treat exit 0 as proof that the selected test ran.

Suite-level `status` values seen: `passed`, `failed`, and `focused`. `focused` means that the file ran with at least one test not executed. It appeared for `only.test.js` and for `allskip.test.js`, and both files exited 0 with `success: true`. A suite-level `skipped` exists in the formatter code of both versions (`formatTestResults`), but no run here produced it.

Counts for `only.test.js`, both versions: `numTotalTests 3, numPassedTests 1, numPendingTests 1, numTodoTests 1`. For `allskip.test.js`: `numTotalTests 2, numPendingTests 1, numTodoTests 1, numPassedTestSuites 1`.

## Bullet 3: a suite that fails to load

Observed on both versions. Four files fail before any test is collected: `syntax`, `missing`, `throws` and `empty`.

```json
{
  "assertionResults": [],
  "coverage": {},
  "message": "  ● Test suite failed to run\n\n    Jest encountered an unexpected token\n\n    Jest failed to...",
  "name": "/private/tmp/ta-jest-29/tests/syntax.test.js",
  "status": "failed",
  "summary": ""
}
```

Top-level counts for `syntax.test.js`, both versions:

```json
{ "numFailedTestSuites": 1, "numFailedTests": 0, "numRuntimeErrorTestSuites": 1,
  "numTotalTests": 0, "numPassedTests": 0, "numPendingTests": 0, "numTodoTests": 0 }
```

- The suite has `status: "failed"`, an empty `assertionResults`, and a `message` that starts with `● Test suite failed to run`. The next lines name the cause.
- `numRuntimeErrorTestSuites` is 1, `numFailedTests` is 0 and `numTotalTests` is 0. This agrees with requirements 4.2: the failed-to-load suite is not counted as a test.
- The cause text differs by case. The first lines after the marker were:

  | File | Text after `Test suite failed to run` |
  |------|---------------------------------------|
  | `syntax.test.js` | `Jest encountered an unexpected token` |
  | `missing.test.js` | `Cannot find module './does-not-exist' from 'tests/missing.test.js'` |
  | `throws.test.js` | `boom at load` |
  | `empty.test.js` | `Your test suite must contain at least one test.` |

- An empty file (no test) is also reported this way, as a suite that failed to run.
- A suite-level `status: "failed"` also appears for an ordinary test failure. To tell the two apart, use `assertionResults` empty plus the `Test suite failed to run` marker in `message`, or use the `numRuntimeErrorTestSuites` count. A per-suite flag does not exist in the JSON.
- A `beforeAll` that throws is not a load failure. `hook.test.js` gave `numTotalTests: 2`, `numFailedTests: 2`, `numRuntimeErrorTestSuites: 0`. Both tests (`Hook a` and `Hook b`) have `status: "failed"` and the same `beforeAll broke` error.

## Bullet 4: is `fullName` stable?

Observed on both versions.

- `fullName` is `ancestorTitles` joined by one space, then `title`. Example: `ancestorTitles: ["Cart", "nested"]`, `title: "works in nested describe"` gives `"Cart nested works in nested describe"`. A top-level test has `ancestorTitles: []` and `fullName` equal to `title`.
- Across three whole-folder runs and one run with `--maxWorkers=1`, the set of `(file, fullName, status)` rows was identical on both versions (19 tests in 8 files). The order of the files in `testResults` was not the same. The adapter must compare sets, not positions.
- `test.each` with `%i` gives distinct titles (`each case 1`, `each case 2`). `fullName` is `Cart each case 1`.
- Titles with regex characters are kept as written. `Cart has [brackets] and (parens) and $dollar` is the `fullName`. A `-t` pattern with the characters escaped (`'^Cart has \[brackets\] and \(parens\) and \$dollar$'`) ran that one test only (1 passed, 11 pending, exit 0) on both versions.
- The same escaped pattern worked for a nested test (`'^Cart nested works in nested describe$'`) and for a `test.each` case (`'^Cart each case 1$'`). In each case one test ran and the others were `pending`.
- Two tests with the same title in one file have the same `fullName`. In `dup.test.js` both entries are `"Dup same title"`, one `passed` and one `failed`. A `-t '^Dup same title$'` run executed both (exit 1). This agrees with requirements 6.4: such a test cannot be selected by name alone, and the adapter must retry it at file level.

Finding for the adapter: `fullName` is stable enough to build the `-t` pattern, if it is regex-escaped and if the title is unique in the file. The adapter must check uniqueness itself, by counting equal `fullName` values per file in the JSON.

## Results per version

| Question | jest 29.7.0 | jest 30.5.2 |
|----------|-------------|-------------|
| JSON shape | As above | The same top-level and suite keys. Each assertion adds `failing`, `retryMessages`, `startAt` |
| File of a test | `testResults[].name`, absolute path | The same |
| `location` without `--testLocationInResults` | `null` | `null` |
| `location` with `--testLocationInResults` | `{line, column}` of the definition | The same, same numbers |
| Line of a failure | First `at path:line:col` frame in `failureMessages[0]` | The same |
| `test.skip`, `xit`, skipped group | `pending` | `pending` |
| `test.todo` | `todo` | `todo` |
| `skipped`, `disabled` on a test | Not seen | Not seen |
| Suite status with unexecuted tests | `focused` | `focused` |
| Load failure | Suite `failed`, empty `assertionResults`, message `Test suite failed to run`, `numRuntimeErrorTestSuites` 1 | The same |
| `beforeAll` throws | Each test `failed`, `numRuntimeErrorTestSuites` 0 | The same |
| `fullName` stable across runs | Yes | Yes |
| Duplicate title in one file | Same `fullName` twice | Same `fullName` twice |
| `-t` matching nothing | Exit 0, all `pending` | Exit 0, all `pending` |

## Effect on requirements 6.2

- Bullet "which `file` and `line` information the JSON provides": answered above. The file is `name`. The failure line is in the stack frame. `--testLocationInResults` adds the definition position only, so it is optional.
- Bullet "how `pending`, `todo`, `skipped` and `disabled` appear": `pending` and `todo` appear as test statuses. `skipped` and `disabled` were not produced by any case tried. The 4.2 mapping for jest should list `pending` and `todo` as skipped, and may keep `skipped` and `disabled` as defensive entries.
- Bullet "a suite that fails to load": answered above. It matches 4.2 (`error: collection`, not counted).
- Bullet "`fullName` stable enough for `-t`": yes, with escaping, and with the duplicate-title rule from 6.4.

## What is not verified

- Windows. Paths in `name` and in stack frames were seen only as macOS paths (`/private/tmp/...`). The form of drive letters and backslashes is not known.
- Other versions. Only jest 29.7.0 and 30.5.2 were run. Other 29.x and 30.x releases, and jest 28 or older, were not run.
- The legacy `jest-jasmine2` runner and custom runners. Only jest-circus ran.
- A test-level `skipped` or `disabled` status, and a suite-level `skipped` status. No sample produced them. Cases such as `--onlyChanged`, `--shard`, `--bail` and `testPathIgnorePatterns` were not tried.
- `--coverage` and the json-summary reporter (requirements 6.5).
- `retry` settings (`jest.retryTimes`), where `invocations` and `retryReasons` change.
- Concurrent tests (`test.concurrent`), `--randomize`, `describe.each`, and `fullName` clashes between different nesting, such as `describe('A B')` with `test('c')` against `describe('A')` with `test('B c')`. The join rule suggests a clash, but no run was made.
- Transformed code (TypeScript or Babel). Stack frames then pass through source maps, and the line may differ. Only plain JavaScript ran.
- Timeout behaviour and stdout progress parsing (requirements 6.3). Those belong to another check.
- Large output, many files, and watch mode.
- Node versions other than v26.13.0.

## Why no script is kept

The captures came from a POSIX `sh` loop with `python3` for inspection and `npx` for running jest. That script uses `/tmp` paths, `sh`, `python3` and shell redirection, so it does not run on Windows. It is not kept in the repo. The commands above are the full method, and the sample files are listed in full or in the table. To repeat the check: create the two scratch folders, install the two jest versions, write the sample files, and run the commands.
