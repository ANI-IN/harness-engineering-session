# Exercise 02: snr-calculator

## Objective

Fix the relevance rule so the calculator reports each task's true
instruction signal-to-noise, matching the shared expected report.

## Why this matters

[Lecture 04](../../README.md)'s case against the giant instruction file is
quantitative: most of what a task loads is noise for that task. The metric
only means something if "signal" is measured honestly, and the starter's
mistake is the honest-looking way to get it wrong: counting every line
that *mentions* a topic as if it *instructed* about it, which flatters the
monolith by exactly the lines that make it bloated.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Demo](../../README.md#demo) and its instruction format
  ([../../code/SPEC.md](../../code/SPEC.md)).
- [Exercise 01](../exercise-01-router-validator/), which keeps the shape
  this metric argues for.

## Provided

- [`SPEC.md`](./SPEC.md): the relevance rule and the summation rule
  (shared).
- [`fixtures/tree/AGENTS.md`](./fixtures/tree/AGENTS.md): the demo's
  45-line monolith, whose prose mentions "api" and "db" outside
  instruction lines (shared).
- [`fixtures/tasks.json`](./fixtures/tasks.json): three tasks (shared).
- [`expected/snr-report.json`](./expected/snr-report.json): the grading
  authority (shared; never edit it).
- `starter/{python,typescript}/main.py|ts`: report plumbing works;
  `relevant_count` counts topic-word mentions.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file, in `relevant_count` /
`relevantCount`.

1. Replace the substring test with the SPEC's rule: a line is relevant
   only when it is an instruction line (the rule regex, already defined)
   whose topic tag is one of the task's topics.
2. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the tag rule stops counting prose
mentions, which corrects every task's `relevant_lines` and therefore
`snr` and `mean_snr` to the expected report's values.

## Expected outcome

Before your change:

```text
[FAIL] basic (python) -- stdout mismatch vs expected/snr-report.json: diverges at $.mean_snr: 0.1259259259259259 != 0.08148148148148149
```

The inflated average (it surfaces before the per-task rows because report
keys compare in sorted order). After your change the report matches
`expected/snr-report.json`, and:

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
<summary>Hint 1: the regex is already there</summary>

The solution to the whole exercise is using `RULE_RE` (already imported
into scope) instead of a substring test, then checking the captured tag
against the task's topics.

</details>

<details>
<summary>Hint 2: which lines inflate the naive count</summary>

Run the starter and diff its `relevant_lines` against the expected
report's; the difference per task is exactly the prose lines mentioning
that task's topic words ("Some api history...", "Older db notes..."). The
fixture keeps them because real monoliths are full of them.

</details>

## Solution walkthrough

One rule change, two lessons riding on it:

- **Mentions are cost, not signal.** The prose lines still count in
  `loaded_lines` (the agent pays to read them) while contributing nothing
  actionable; the naive rule counted them on both sides of the fraction,
  which is how bloated files defend themselves with their own bloat.
- **The average leaked the bug first.** The divergence surfaced at
  `mean_snr`, not at a per-task row, because canonical comparison walks
  keys in sorted order. Knowing *where* your differ reports a divergence
  is part of reading it; the per-task rows carry the same story one level
  deeper.

Cross-track note: both tracks share the summation rule pinned by the demo
SPEC (plain left-to-right accumulation), which exists because Python's
`sum()` compensates floating-point error and JavaScript's `reduce` does
not; this exercise inherits that rule rather than rediscovering it.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-04-why-one-giant-instruction-file-fails/exercises/exercise-02-snr-calculator -->
```text
starter/python: exit 1 (as intended: diverges at $.mean_snr: 0.1259259259259259 != 0.08148148148148149)
starter/typescript: exit 1 (as intended: diverges at $.mean_snr: 0.1259259259259259 != 0.08148148148148149)
solution/python: exit 0 (PASS: pass (1 check))
solution/typescript: exit 0 (PASS: pass (1 check))
4/4 acceptance runs performed
```
<!-- /generated-block -->
