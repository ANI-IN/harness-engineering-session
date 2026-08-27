# Exercise 02: rebuild-cost

## Objective

Fix the savings orientation so the comparison states what the continuity
artifacts buy, with positive numbers always meaning the handoff won.

## Why this matters

[Lecture 05](../../README.md)'s demo produced two runs of the same task;
this exercise makes you compute the difference, which is where continuity
stops being a feeling and becomes a cost model. The starter's mistake is
the classic one in any before/after comparison: one subtraction direction
applied to metrics that point opposite ways, which silently reports the
intervention as harmful.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Demo](../../README.md#demo) (where the fixture reports
  come from) and [exercise 01](../exercise-01-handoff-roundtrip/).

## Provided

- [`SPEC.md`](./SPEC.md): the orientation rule (shared).
- [`fixtures/reports/`](./fixtures/reports/): the demo's committed
  with-handoff and no-handoff reports, copied verbatim (shared; their
  figures originate from the demo's fixtures).
- [`expected/rebuild-cost.json`](./expected/rebuild-cost.json): the
  grading authority (shared; never edit it).
- `starter/{python,typescript}/main.py|ts`: plumbing works; `savings`
  subtracts in one fixed direction.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file, in `savings`.

1. Orient the three cost metrics (reacquisition lines, rework sessions,
   drift events) as without-handoff minus with-handoff.
2. Orient the completion metric (features completed) as with-handoff minus
   without-handoff.
3. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the corrected orientation flips the sign
of all four savings to the expected report's values.

## Expected outcome

Before your change:

```text
[FAIL] basic (python) -- stdout mismatch vs expected/rebuild-cost.json: diverges at $.savings.drift_events: -2 != 2
```

After your change every saving is positive (the handoff mode wins on all
four metrics for these fixtures), and:

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
<summary>Hint 1: sort the metrics by what "more" means</summary>

Reacquisition lines, rework sessions, and drift events are costs: more is
worse, so the saving is what the no-handoff run paid extra. Features
completed is the opposite. Orient each metric by its meaning, not by a
uniform formula.

</details>

<details>
<summary>Hint 2: the fixture makes wrong signs obvious</summary>

On these fixtures every correctly-oriented saving is positive. If any of
your four comes out negative, that metric's subtraction is backwards.

</details>

## Solution walkthrough

One function, one modeling point:

- **Orientation is semantics, not arithmetic.** The naive version is
  internally consistent and wrong: it answers "how much more did the
  handoff run cost?" for every metric, including the one where more is
  better. Comparisons need a declared convention (here: positive = the
  intervention won), and the SPEC states it precisely so both tracks and
  every reader agree on what a sign means.
- **The dangerous version of this bug survives reviews.** A table of
  plausible-magnitude numbers with flipped signs reads fine until someone
  acts on it; the committed expected report is what makes the sign an
  executable fact here.

Cross-track note: the fix is the same four subtractions in both tracks;
the shared expected report holds them to identical output, including the
integral results of pure-integer arithmetic.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-05-why-long-running-tasks-lose-continuity/exercises/exercise-02-rebuild-cost -->
```text
starter/python: exit 1 (as intended: diverges at $.savings.drift_events: -2 != 2)
starter/typescript: exit 1 (as intended: diverges at $.savings.drift_events: -2 != 2)
solution/python: exit 0 (PASS: pass (1 check))
solution/typescript: exit 0 (PASS: pass (1 check))
4/4 acceptance runs performed
```
<!-- /generated-block -->
