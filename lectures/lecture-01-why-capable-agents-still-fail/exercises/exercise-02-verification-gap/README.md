# Exercise 02: verification-gap

## Objective

Implement the before-claim verification check so the auditor classifies
every run correctly and computes the true verification gap.

## Why this matters

[Lecture 01](../../README.md) names the verification gap (confident "done"
claims not backed by a passing check) as the most common agent failure mode.
This exercise makes the gap a number you compute, and pins the subtlety that
matters most: a check that runs *after* the claim does not back the claim.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- [Exercise 01](../exercise-01-failure-triage/), whose feedback rule is
  this exercise's core idea in single-rule form.

## Provided

- [`SPEC.md`](./SPEC.md): the contract (shared).
- [`fixtures/claims.jsonl`](./fixtures/claims.jsonl): six runs, including
  the trap run `g6` (claim first, passing check after); and
  [`fixtures/claims-none.jsonl`](./fixtures/claims-none.jsonl), a
  transcript with no claims at all (shared).
- [`expected/gap-report.json`](./expected/gap-report.json) and
  [`expected/no-claims.json`](./expected/no-claims.json): the grading
  authority (shared; never edit these).
- `starter/{python,typescript}/main.py|ts`: working parsing and report
  plumbing; `classify` marks every claimed run unverified.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file, in `classify`.

1. Find the run's first `claim` event (the starter already does this).
2. Determine whether any *earlier* event of the same run is a
   `verification` with `result: "pass"`.
3. Set `verified_before_claim` from that, and classify the run
   `verified-done` or `unverified-done` accordingly.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the before-claim check reclassifies `g1`
and `g5` as `verified-done`, which corrects the three count fields and
turns `verification_gap` from 1.0 into the expected 0.6.

## Expected outcome

Before your change:

```text
[FAIL] basic (python) -- stdout mismatch vs expected/gap-report.json: diverges at $.runs[0].classification: 'unverified-done' != 'verified-done'
```

After your change, the report classifies g1/g5 verified, g2/g3/g6
unverified, g4 no-claim, with `"verification_gap": 0.6`, and:

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

Both fixture transcripts are checked; the no-claims one also pins the rule
that an empty denominator yields the number 0, not a division error.

## Hints

<details>
<summary>Hint 1: the events are already sliced for you</summary>

The starter computes the first claim's index. "Earlier events" means the
events before that index; both languages slice a list/array for exactly
this.

</details>

<details>
<summary>Hint 2: the trap run</summary>

If `g6` comes out `verified-done`, you checked the whole run for a passing
verification instead of only the events before the claim. The order is the
point: victory declared before evidence exists is the gap.

</details>

## Solution walkthrough

The solution is three lines of logic, and both obvious shortcuts are wrong
in instructive ways:

- **Scanning the whole run** instead of the prefix passes five of six runs
  and silently blesses `g6`, the exact pattern the lecture warns about.
  The fixture exists to make that shortcut fail loudly.
- **Counting any verification event** (ignoring `result`) would credit
  `g3`, where the check ran and failed. A failing check is evidence of
  honesty, not of completion; only `result: "pass"` backs a claim.

Cross-track note: Python expresses the prefix check as `any(...)` over a
slice, TypeScript as `.slice(...).some(...)`. The `no-claims` case also
exercises the repository's integral-float rule: Python's `0.0` and
TypeScript's `0` are the same JSON number after normalization.
