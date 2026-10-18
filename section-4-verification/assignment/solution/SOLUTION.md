# Assignment 4: Verification. Solution: verification and portfolio

This folder is a finished implementation folder for [Assignment 4](../README.md): the check for
House rule 8: Deleted issues stay hidden, Filter 6: No duplicate tests, the tests, a skill, the live
evidence, the portfolio, and the captured checks. This page explains
how it was built and why.

> **Terms on this page**
>
> - **House rule 8**: The house rule you add: a soft-deleted issue answers 404 and never appears in a list.
> - **Check**: A shipharness program that probes every endpoint for one rule and reports findings.
> - **Finding**: One violation a check reports, with a rule, an endpoint, a severity, and a detail key.
> - **Baseline**: The findings on the unchanged checkpoint; a check counts only new ones.
> - **Marker**: A title only a soft-deleted test issue carries, so a response that shows it is evidence.
> - **Filter 6**: The filter you add: it discards a test that repeats another test.
> - **Bare arm**: An agent run with the ticket and the repository, and no harness.
> - **Harness arm**: The same run with the harness turned on.
> - **Live evidence**: The files your real runs wrote, collected into `live/`.

What is in this folder:

| Path | What it is |
|---|---|
| `a4_verification/` | The check, the soft-delete adapter, Filter 6, and two command-line tools |
| `tests/` | The solution's own tests |
| `skill/testgen-evidence/` | A skill that turns a testgen report into a short summary |
| `live/` | The live evidence: testgen output and report, A/B output, two score records |
| `portfolio/` | Evidence report, LangSmith page, and case study, filled from `live/` |
| `captured/` | Real output of the self-check, the grade, and the check on TeamTrack |

## The approach, step by step

1. **Soft-delete in the database, not through the API.** The adapter picks the lowest-id live issue
   of each of the home org's projects (issues 1 and 11 in the seed data), sets `deleted_at`, and sets
   the title to a marker such as `[r8-deleted:1]` (`a4_verification/adapter.py`).

2. **Plan probes from the schema, lists first.** `plan` in `a4_verification/r8_soft_delete.py`
   makes one `deleted_list` probe per GET endpoint that does not address an issue, one
   `deleted_body` probe per write whose generated body has `issue_id`, and one `deleted_path` probe
   per endpoint of any method that addresses an issue. On TeamTrack that is 15 probes.

3. **Judge on text, not ids.** `judge` fails a list when a 2xx body contains a marker, a path probe on
   anything but 404, and a body probe on 2xx.

4. **Report through the framework.** Each failure is a `Finding(rule="R8", detail_key=<probe kind>)`.
   Findings pass through `apply_exemptions` and `make_result`, and the check is registered with
   `register_check`. `run_r8` hands everything else to the shipharness check runner, so baselines,
   exit codes, and the JSON document are the framework's own.

5. **Filter 6 on syntax trees.** It parses each test, drops the docstring, renames locals in order of
   first appearance, and compares decorators, parameters, and body
   (`a4_verification/dedup_filter.py`). It remembers the candidates it kept, so a later copy in the
   same run is discarded too.

6. **Run the live step once.** One testgen run on the pinned target
   `TG-teamtrack-app-repositories-issues`, Filter 6 over its kept tests, and one A/B on Feature 4:
   Version checks on issue edits. The portfolio was then written from those files.

## Design choices and why

- **Marker titles.** Project 1, user 1, org 1, and audit rows share the numbers of the deleted issues.
  So "id 1 appears in the body" would flag `GET /projects`, `GET /me`, and `GET /orgs/current` on a
  correct build. A marker only the deleted row can contain makes every list finding a real
  appearance, at any depth and in any response shape. The brackets stop `[r8-deleted:1]` from
  matching inside `[r8-deleted:11]`.
- **Database soft delete.** If the check deleted through `DELETE /issues/{id}`, a build with a broken
  delete endpoint would fail it for the wrong reason. The tenant isolation, roles, and audit log rules
  already probe that endpoint. The cost
  is that the adapter knows one table and one column; that knowledge stays in the adapter.
- **Lists before writes.** A write probe that wrongly succeeds, such as a PATCH that renames the
  issue, would remove the marker. Lists run first, so every list sees every marker.
- **`detail_key` is exactly the probe kind.** `mark_baseline` matches findings on rule, endpoint,
  severity, and detail key. Ids, statuses, and response text stay in `detail`, so the legacy
  `GET /v1/issues` finding matches across runs and counts as baseline.
- **Remediation in the message.** Each `detail` says what to change, such as "add `deleted_at IS
  NULL` to the query". OpenAI's harness team writes its lint messages "to inject remediation
  instructions into agent context"
  ([Harness engineering](https://openai.com/index/harness-engineering/)).
- **Filter 6 outside the default list.** The pipeline takes a list of filters, so Filter 6 runs
  without a change under `platform/src/`. `apply_filter --update-report` adds its rows to the testgen
  report, so one file shows all six filters.
- **Parameters are never renamed.** Two tests that differ only in fixture names use different
  fixtures, so they test different setups.

### Trade-offs and known limits

- One deleted id per path and body probe keeps one probe per endpoint, at the cost of not checking
  every deleted row on every endpoint.
- The marker changes the title of the deleted rows. An endpoint that reformats titles could hide it;
  TeamTrack returns titles as stored.
- A list endpoint with a required query parameter, such as a search term, gets a generated value that
  may filter the deleted rows out. A next step is a probe that sends the marker as the search text.
- Only the first page of each list is read. The deleted rows have the lowest ids, so they are on the
  first page of every list ordered by id.
- The check covers issues only. The handbook says archived projects also "behave as if they do not exist".
- Filter 6 is exact and explainable, but it misses tests that check the same rule through different
  calls.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Find deleted issues by id in response bodies | False findings on every resource that shares the number |
| Soft-delete through `DELETE /issues/{id}` | Couples the check to the delete endpoint working |
| Probe only GET endpoints | Misses writes that resolve a deleted issue |
| A fixed list of issue endpoints in the check | Misses endpoints the build adds |
| Compare test text, or a hash of it | Comments and layout change the text, not the test |
| Token or embedding similarity for duplicates | Not exact, and a discard needs a reason a reader can check |
| Add Filter 6 to the default filter list | Needs a change under `platform/src/`, outside the assignment |

## Common mistakes this avoids

- No id-based evidence, so project, user, and org lists stay clean on a correct build.
- No hand-written endpoint list: a new endpoint gets probed because the schema lists it.
- No response text in `detail_key`, so the legacy finding stays in the baseline.
- No renamed fixtures in Filter 6.
- No number typed by hand in the portfolio: every count and cost comes from the files in `live/`.
- One testgen run and one A/B, each kept as it came out.

## Run and verify it

From the repository root. These commands need no keys and no Docker:

```bash
make check-assignment-4 A4_IMPL=section-4-verification/assignment/solution
PYTHONPATH=section-4-verification/assignment/solution uv run python -m pytest -q -p no:cacheprovider section-4-verification/assignment/solution/tests
PYTHONPATH=section-4-verification/assignment/solution uv run python -m a4_verification.run_r8 --build platform/teamtrack --checkpoint m1-base --feature A4
```

> Your output will differ: your own live runs are other agent sessions, so their counts, costs, and
> links will not match the ones below.

When captured, the self-check ended like this (the full output is in
`captured/self-check-solution.txt`):

```text
[live-evidence]
  PASS test_live_testgen_run
  PASS test_live_testgen_report_shows_filter_6
  PASS test_live_ab_command_and_cost
  PASS test_live_ab_score_records
...
self-check: PASSED (23/23 visible tests pass)
Next: submit this folder with its live/; the grader adds the hidden tests.
Cost: $0.000000 (no model calls)
```

The House rule 8 check on TeamTrack finds one counted problem, `GET /v1/issues` (`deleted_list`, severity `leak`), in 15
probes. The full JSON is in `captured/r8-teamtrack.json`.

## Evidence

The live testgen run, from `live/testgen.txt` (paths shortened for privacy; the run id is cut to `<run id>`; three of the four
lines for Filter 3: Adds coverage or catches a mutant are cut where `...` shows):

```text
$ uv run shipharness testgen --target TG-teamtrack-app-repositories-issues --max-tests 10 --out .shipharness/a4/testgen
target TG-teamtrack-app-repositories-issues: app/repositories/issues.py in ~/shipharness/teamtrack
! UNSANDBOXED — results not official: generated tests run on this machine
Baseline: existing suite without doctests
testgen <run id>: completed; kept 1 of 5 proposed tests
+ tests/visible/test_issue_repository.py::test_list_for_project_uses_ascending_keyset_pages
- tests/visible/test_issue_repository.py::test_add_flushes_issue_with_requested_fields_and_database_defaults: filter 3: adds no line coverage over the existing suite and kills no filter-set mutant that the existing tests miss (0 checked)
...
Kept tests and report: .shipharness/a4/testgen
Cost: $0.003287 (testgen, model gpt-6-luna)
```

Filter 6 then kept that one test: it repeats none of the 23 existing tests it was compared with
(`filter6` in `live/testgen-report.json`).

The live A/B on Feature 4 (`F4` in the output), from `live/ab.txt` (the A/B id is
cut to `<run id>`, the running totals to `...`):

```text
$ uv run shipharness ab --section demo-4 --feature F4 --purpose assignment --no-preview
A/B <run id> (F4, layers=['instructions', 'scope', 'state', 'verify'], profile=standard)
  bare     completed         claim=none     primary={"hidden_passed": 68, "mutants_killed": 4} passed=False hidden 68/69 mutants 4/4 reviewer=reject cost=$0.0185
  harness  ABORTED: timeout  claim=none     primary={"hidden_passed": 43, "mutants_killed": 0} passed=False hidden 43/69 mutants 0/4 reviewer=reject cost=$0.0162
Cost: $0.042138 (this command: gpt-5.6-luna $0.007424, gpt-6-luna $0.034714; ...)
```

Neither arm passed the primary measure. The live-evidence criterion grades the files, not which arm
won, so this run is an example of evidence, not a result about the harness.

The instructor's grade of this folder, from `make grade-assignment-4
SUBMISSION=section-4-verification/assignment/solution` (the grader is not in this repository; the full
output is in `captured/grade-solution.txt`; the `R8-` criteria grade the House rule 8 check, the
`F6-` ones Filter 6):

```text
Criterion                     Points  Tests
R8-interface                     5/5  5/5
R8-visible                       9/9  2/2
R8-hidden                      17/17  6/6
R8-no-false-positives            8/8  4/4
R8-baseline                      7/7  4/4
F6-interface                     4/4  2/2
F6-visible                       6/6  3/3
F6-hidden                      13/13  12/12
own-tests                        5/5  2/2
skill                            6/6  1/1
portfolio-evidence               5/5  1/1
portfolio-langsmith              2/2  1/1
portfolio-case-study             3/3  1/1
live-evidence                  10/10  4/4

Score: 100/100
```

Dates, run ids, and the capture details for all of the above are on the
[evidence page](../../../docs/evidence/s4.md#s4-a4-solution).

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world, <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
