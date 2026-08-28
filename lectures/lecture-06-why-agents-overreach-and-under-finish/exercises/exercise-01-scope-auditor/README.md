# Exercise 01: scope-auditor

## Objective

Fix the in-scope rule so the auditor separates work on the active
feature from drift into queued and invented features, matching both
shared expected reports.

## Why this matters

[Lecture 06](../../README.md)'s claim is that overreach is a state you
can read off a session, and the change log is where you read it. The
starter's mistake is the overreach rationalization written as code: "the
feature is on the plan, so working on it is fine". The plan is scope for
later sessions; only the active feature is scope for this one, and an
auditor that cannot tell the two apart certifies exactly the sessions
the lecture's open workspace produced.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Demo](../../README.md#demo) and the scope surface it
  reads ([../../code/SPEC.md](../../code/SPEC.md)).
- The glossary's [scope surface](../../../../docs/glossary.md#working-discipline)
  entry: work outside it is overreach by definition.

## Provided

- [`SPEC.md`](./SPEC.md): the contract and the starter's naive rule
  (shared).
- [`fixtures/feature_list.json`](./fixtures/feature_list.json): four
  features, `search-endpoint` active, three queued (shared).
- [`fixtures/changes/clean-session.json`](./fixtures/changes/clean-session.json)
  and [`fixtures/changes/mixed-session.json`](./fixtures/changes/mixed-session.json):
  a session that stayed inside the boundary and one that drifted into a
  queued feature twice and an invented feature once (shared).
- [`expected/clean-session.json`](./expected/clean-session.json) and
  [`expected/mixed-session.json`](./expected/mixed-session.json): the
  grading authority (shared; never edit them).
- `starter/{python,typescript}/main.py|ts`: report shape, active-feature
  header, drift bookkeeping, and CLI all work; the in-scope test asks the
  wrong question.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file, in `audit`.

1. A change is in scope only when its feature is active (`in-progress`),
   with reason `targets the active feature`.
2. A change to a listed but inactive feature is drift with reason
   `<id> is in the queue, not active`.
3. A change to a feature the list does not know stays drift with reason
   `<id> is not in the feature list`.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the active-only rule flips the two
queued-feature changes in `mixed-session` to `in_scope: false` with the
queue reason, which also corrects the drift count and feature list to
the expected values.

## Expected outcome

Before your change:

```text
[FAIL] mixed-session (python) -- stdout mismatch vs expected/mixed-session.json: diverges at $.changes[1].in_scope: True != False
```

The first queued-feature change is classified as in scope. After your
change both cases match, and:

```text
verify: PASS (starter)
```

## How to verify

### Python

```sh
./verify.sh --stack=python
```

### TypeScript

```sh
./verify.sh --stack=typescript
```

## Hints

<details>
<summary>Hint 1: two sets, not one</summary>

The starter already builds the list of active ids for the report
header. The membership test needs that set, and the listed set is still
useful: it is what separates "queued" from "unknown".

</details>

<details>
<summary>Hint 2: three outcomes, in order</summary>

Test active first, then listed, then everything else. Each branch owns
one reason string; the SPEC's "The rule" section has all three verbatim.

</details>

## Solution walkthrough

The fix is a three-way classification where the starter had a two-way
one:

- **Active** means in scope. Not "listed", not "related", not "on the
  roadmap": the single `in-progress` entry (or entries, if a workspace
  allows more) is the whole scope of this session.
- **Queued** drift is the lecture's overreach exactly: planned work,
  started early, at the cost of the work that was assigned. It gets its
  own reason so the report distinguishes it from the next kind.
- **Unknown** drift is the session inventing scope (`session-metrics`
  never existed in the list). Both kinds count toward `drift.count`;
  both land in `drift.features` once, in first-seen order.

The verdict is the exit code because that is what a session-end gate
consumes. Cross-track note: both tracks keep `drift.features` in
first-seen order with a linear membership check rather than a set, so
the arrays match without sorting; the conformance runner holds the two
reports byte-identical.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-06-why-agents-overreach-and-under-finish/exercises/exercise-01-scope-auditor -->
```text
starter/python: exit 1 (as intended: diverges at $.changes[1].in_scope: True != False)
starter/typescript: exit 1 (as intended: diverges at $.changes[1].in_scope: True != False)
solution/python: exit 0 (PASS: pass (3 checks))
solution/typescript: exit 0 (PASS: pass (3 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
