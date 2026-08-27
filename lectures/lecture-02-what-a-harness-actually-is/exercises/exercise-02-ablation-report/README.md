# Exercise 02: ablation-report

## Objective

Implement the ablation comparison so six loop reports collapse into one
controlled-variable table: what removing each subsystem changed against the
baseline.

## Why this matters

[Lecture 02](../../README.md) argues every subsystem earns its place, and
the way to test that is controlled-variable ablation: remove exactly one
component, re-run the same task, compare. The demo produced the six runs;
this exercise makes you build the comparison, which is the part people skip
when they eyeball outputs instead of diffing them.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Demo](../../README.md#demo) section (where the six
  fixture reports come from) and
  [exercise 01](../exercise-01-subsystem-auditor/).

## Provided

- [`SPEC.md`](./SPEC.md): the comparison rules (shared).
- [`fixtures/reports/`](./fixtures/reports/): the demo's six committed
  reports, copied verbatim: `full.json` plus five `disable-*.json` (shared;
  their figures come from the demo's fixtures, not from prose).
- [`expected/ablation-report.json`](./expected/ablation-report.json): the
  grading authority (shared; never edit it).
- `starter/{python,typescript}/main.py|ts`: loading and aggregation work;
  the comparison reports nothing changed.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file, in `compare`.

1. Set `outcome_changed`: the ablated run's outcome differs from the
   baseline's outcome.
2. Set `signature`: the ablated run's first issue string, or null/None when
   it has none.
3. Re-run verification until it exits 0 (`all_degraded` follows from your
   `outcome_changed` values; the plumbing already computes it).

What makes `verify.sh` flip to 0: correct `outcome_changed` and `signature`
values flip all five ablation rows and `all_degraded` to the expected
report's values.

## Expected outcome

Before your change:

```text
[FAIL] basic (python) -- stdout mismatch vs expected/ablation-report.json: diverges at $.ablations[0].outcome_changed: False != True
```

After your change: five ablation rows each with `outcome_changed: true`,
each carrying its characteristic signature, `all_degraded: true`, and:

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
<summary>Hint 1: both fields come straight from the two reports</summary>

`compare` receives the baseline report and one ablated report. The outcome
strings are top-level fields; the issues list is too. No file I/O is needed
inside `compare`.

</details>

<details>
<summary>Hint 2: the empty-issues edge</summary>

The baseline has no issues; an ablated report always does in these
fixtures, but the SPEC still requires the null case (first issue *or*
null). Python: a conditional expression. TypeScript: index and coalesce.

</details>

## Solution walkthrough

The comparison is two lines per field, and the design point is what it
refuses to do:

- **It compares against the baseline, not against "success".** An ablation
  study needs a fixed reference run; hardcoding "completed-verified" as the
  comparison target happens to work here and silently breaks the moment the
  baseline itself degrades, which is exactly when you most need the report
  to say so.
- **The signature is evidence, not a summary.** Carrying the first issue
  string forward keeps each row traceable to the run that produced it, the
  same evidence discipline the course applies to feature lists.

Cross-track note: Python's `issues[0] if issues else None` and TypeScript's
`ablated.issues[0] ?? null` are each language's idiom for the same rule,
and the shared expected report holds both to the same bytes. The fixture
reports themselves are the demo's committed outputs, so this exercise's
numbers are regenerated whenever the demo's are.
