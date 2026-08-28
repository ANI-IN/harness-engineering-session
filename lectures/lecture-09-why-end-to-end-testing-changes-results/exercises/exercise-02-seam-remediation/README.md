# Exercise 02: seam-remediation

## Objective

Fix a remediation writer that tells the next session to change whichever
component objected, so that every fix instruction names the component that
produced the offending value and the report matches all four shared
expected outputs.

## Why this matters

[Lecture 09](../../README.md) ends with a failing end-to-end run and a
message. The message is what the next session acts on, and it decides
which of two very different edits happens. Told that `file-writer`
rejected a relative path, a session can make `file-writer` accept relative
paths: the run goes green, the export still lands in the wrong place, and
the check that caught the defect is gone. Told that `path-builder` emitted
a relative path where `file-writer` requires an absolute one, the same
session fixes the export. The starter writes the first message every time,
and the third fixture shows where that habit ends: a flow that finishes
with the wrong artifact, and an instruction to change what the flow
expects.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Implementation notes](../../README.md#implementation-notes)
  on the producer as the fix site, and the demo contract's op vocabulary
  ([../../code/SPEC.md](../../code/SPEC.md)).
- [Exercise 01](../exercise-01-assembled-run/), which builds the assembled
  run whose failures this exercise turns into instructions.

## Provided

- [`SPEC.md`](./SPEC.md): the contract, the three failure kinds with their
  exact `what`, `why`, and `fix` shapes, and the starter's naive decision
  (shared).
- [`fixtures/workspaces/workspace-seam-gap`](./fixtures/workspaces/workspace-seam-gap/):
  a `prefix` failure, the relative path a writer will not take (shared).
- [`fixtures/workspaces/workspace-name-gap`](./fixtures/workspaces/workspace-name-gap/):
  a `missing` failure, where nothing in the flow ever wrote the field the
  service reads (shared).
- [`fixtures/workspaces/workspace-artifact-gap`](./fixtures/workspaces/workspace-artifact-gap/):
  the trap. Every stage accepts the record, `file-writer` writes
  `<path>.tmp` exactly as its own unit case declares, and the flow ends
  holding the wrong artifact (shared).
- [`fixtures/workspaces/workspace-seam-closed`](./fixtures/workspaces/workspace-seam-closed/):
  nothing to remediate (shared).
- [`expected/`](./expected/): the four grading reports (shared; never edit
  them).
- `starter/{python,typescript}/main.py|ts`: the assembled run, the failure
  record, the producer lookup, and the `what` and `why` lines are
  complete; only the `fix` line is naive.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. Rewrite `fix_line` (`fixLine` in TypeScript) so each instruction is
   addressed to `failure["producer"]`, the component that last wrote the
   offending field, using the three shapes SPEC.md pins.
2. Leave `what` and `why` alone: naming the objection and the contract it
   states is correct reporting, and the instruction is what has to move.
3. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the producer is already computed and
carried on the failure record, so each instruction changes target while
the counts, the verdict, and the exit codes stay exactly as they are;
`clean-flow-has-nothing-to-fix` never had an instruction to get wrong.

## Expected outcome

Before your change:

```text
  [FAIL] prefix-seam-remediated (python) -- stdout mismatch vs expected/seam-gap.json: diverges at $.remediations[0].fix: 'change file-writer to accept path=exports/quarterly.csv' != 'change path-builder to emit path starting with /'
  [FAIL] missing-field-remediated (python) -- stdout mismatch vs expected/name-gap.json: diverges at $.remediations[0].fix: 'change path-builder to accept a record without report' != 'change selection-ui to emit report before path-builder runs'
  [FAIL] wrong-artifact-remediated (python) -- stdout mismatch vs expected/artifact-gap.json: diverges at $.remediations[0].fix: 'change assembled-export-flow to expect written=/srv/reports/exports/quarterly.csv.tmp' != 'change file-writer to emit written=/srv/reports/exports/quarterly.csv'
  [pass] clean-flow-has-nothing-to-fix (python)
```

Read the three left-hand strings together: each one removes a check rather
than a defect. After your change all four cases match, and:

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
<summary>Hint 1: the value you need is already there</summary>

`run_pipeline` attaches `producer` to every failure before returning it.
The naive version reads `failure["stage"]` in all three branches; the
field it should be reading is one key away.

</details>

<details>
<summary>Hint 2: the shapes are pinned, so match them exactly</summary>

SPEC.md gives all three `fix` templates literally. The `missing` shape
still mentions the objecting stage (`before <stage> runs`), because the
instruction needs to say when the field has to exist; only the component
being asked to change moves.

</details>

<details>
<summary>Hint 3: the artifact case has no rejecting component</summary>

In `workspace-artifact-gap` no stage refuses anything, so the objection
comes from the flow's own `expects`. The producer there is whatever last
wrote the field, which is `file-writer`. The naive instruction rewrites
the expectation to match the code, which is the same move in its purest
form.

</details>

## Solution walkthrough

The three branches change one name each, from the objecting stage to the
producer, and the rest of the report stands. What that swap encodes is an
ordering rule: the component that states a constraint is the authority,
and the value that violated it has to change upstream. The starter is not
lazy, it is locally reasonable, which is why the habit survives: every one
of its instructions makes the failing run pass. The `missing` shape keeps
both names, the producer to change and the stage that has to see the field,
because an instruction that says only "emit report" does not say by when.
The reference practice this implements is a failure message written for
the next agent rather than for a log reader: what happened, why it is a
violation, and the concrete edit.
[Project 05](../../../../projects/project-05-self-verification-and-role-separation/)'s
checker writes verdicts in the same register, naming the change rather
than the complaint. Cross-track note: both tracks build the instruction
from the same failure record, so the strings are identical across the two
without any per-language formatting.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-09-why-end-to-end-testing-changes-results/exercises/exercise-02-seam-remediation -->
```text
starter/python: exit 1 (as intended: diverges at $.remediations[0].fix: 'change file-writer to accept path=exports/quarterly.csv' != 'change path-builder to emit path starting with /')
starter/typescript: exit 1 (as intended: diverges at $.remediations[0].fix: 'change file-writer to accept path=exports/quarterly.csv' != 'change path-builder to emit path starting with /')
solution/python: exit 0 (PASS: pass (4 checks))
solution/typescript: exit 0 (PASS: pass (4 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
