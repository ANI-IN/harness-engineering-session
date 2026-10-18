# Case study: making "deleted means gone" a checked rule

Reference version. The run numbers come from the reference solution's live run, captured on
2026-10-17 (`../live/`).

## Problem

TeamTrack's handbook says a deleted issue behaves as if it does not exist: 404 on read, hidden
from lists. Nothing checked that. A coding agent that adds an endpoint can query the issues table
without the `deleted_at` filter, and the visible tests still pass, because no visible test deletes
an issue first. OpenAI's harness team describes the fix: rules the team cares about become checks, "enforced mechanically via custom linters ... and structural tests"
([Harness engineering](https://openai.com/index/harness-engineering/)).

## What I built

- A check for House rule 8: Deleted issues stay hidden, in the shipharness check framework. It reads the app's OpenAPI schema,
  soft-deletes the first issue of each project directly in the database, gives those rows a marker
  title, and probes every endpoint as an admin: lists must not show a marker, any operation that
  addresses a deleted issue must answer 404, and a write that names a deleted issue in its body
  must fail.
- Filter 6: No duplicate tests, for the test pipeline: a proposed test that repeats an existing test,
  or a test kept earlier in the same run, is discarded with the name of the test it copies. Meta's
  test generator added a filter "to remove previously seen test cases"
  ([Automated Unit Test Improvement using Large Language Models at Meta](https://arxiv.org/abs/2402.09171));
  this one also ignores renamed local variables, a course choice.
- A skill, `testgen-evidence`, that turns a testgen run into an evidence report.

## Evidence

- On a TeamTrack copy the grader seeds faults the visible tests do not show: a new list endpoint,
  a deleted issue nested inside a board response, a write-only lookup, a `{id}` path parameter, an
  issue parameter after a project parameter, and an issue id in a request body. The check reports
  each at the right endpoint and nothing on correct versions (`../captured/grade-solution.txt`).
- On TeamTrack itself the check makes 15 probes and finds one violation, the legacy list
  (`evidence-report.md`).
- Testgen on `app/repositories/issues.py` (one run, $0.003287) proposed 5 tests and kept 1; Filter
  3: Adds coverage or catches a mutant discarded the other 4: no new coverage and no mutant (planted fault) caught beyond the existing
  suite. Filter 6 removed none: the kept test copies none of the 23 existing tests
  (`evidence-report.md`).
- The live A/B on Feature 4: Version checks on issue edits (`langsmith.md`): the bare arm passed 68 of 69 hidden
  tests and caught 4 of 4 planted faults; the harness arm stopped on a
  timeout with 43 of 69 and 0 of 4. Neither passed the primary measure, and one run per arm is an
  example, not a rate.

## What I learned

The marker title mattered more than the probes. My first idea was to look for the deleted issue's
id in each response, but project 1, user 1, and org 1 share that number, so every list of projects
would have been a finding. A marker only the deleted row carries removes that class of false
positive. The second lesson is about baselines: a check that reports the legacy handler on
every run is noise unless its findings match across runs, which is what `detail_key` is for.
Anthropic's compiler team warns that "it is easy to see tests pass and assume the job is done, when
this is rarely the case" ([Building a C compiler](https://www.anthropic.com/engineering/building-c-compiler));
seeded faults are how I found out whether my own check was done.

## Next steps

- Probe search endpoints with the marker as the query text.
- Extend the adapter to archived projects, which the handbook treats the same way.
- Run Filter 6 inside `shipharness testgen` rather than after it.

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world, <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
- Source 2: Automated Unit Test Improvement using Large Language Models at Meta, <https://arxiv.org/abs/2402.09171>,
  Alshahwan et al. (Meta), 2024-02-14
- Source 3: Building a C compiler with a team of parallel Claudes, <https://www.anthropic.com/engineering/building-c-compiler>, Nicholas Carlini (Anthropic), 2026-02-05
