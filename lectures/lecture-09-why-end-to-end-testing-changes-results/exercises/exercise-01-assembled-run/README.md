# Exercise 01: assembled-run

## Objective

Fix an end-to-end layer that runs the right components in the right order
without ever wiring them together, so that one record is threaded through
the pipeline and the report matches all three shared expected outputs.

## Why this matters

[Lecture 09](../../README.md)'s claim is that the kind of check decides the
result, and the kind that changes it is a run through the assembled
system. The word "assembled" is doing the work. A runner that loops over
the pipeline's stages and executes each one looks like an end-to-end
runner, produces an end-to-end report, and fills the `e2e` slot in a
definition of done. If each stage starts from its own unit fixture, it has
crossed no seam and can catch nothing a unit check could not. The starter
is that runner, and the fixtures show what it costs: on the workspace
where the fixtures happen to agree with the flow it is indistinguishable
from the real thing, and on the two where they do not it reports a
finished export for an application that cannot export.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Demo](../../README.md#demo) and the demo contract's op
  vocabulary and layer semantics ([../../code/SPEC.md](../../code/SPEC.md)).
- The glossary's
  [seeded defect](../../../../docs/glossary.md#verification-machinery-this-repositorys-own)
  entry: a fixture broken on purpose, with its symptom and catching stage
  declared.

## Provided

- [`SPEC.md`](./SPEC.md): the contract, the report shape, and the
  starter's naive decision (shared).
- [`fixtures/workspaces/workspace-seam-gap`](./fixtures/workspaces/workspace-seam-gap/):
  the trap. `path-builder` emits a relative path, `file-writer` accepts
  only absolute ones, and both unit cases pass (shared).
- [`fixtures/workspaces/workspace-name-gap`](./fixtures/workspaces/workspace-name-gap/):
  `selection-ui` writes `report_name`, `path-builder` reads `{report}`
  (shared).
- [`fixtures/workspaces/workspace-seam-closed`](./fixtures/workspaces/workspace-seam-closed/):
  the seam agrees, and every component's unit case input happens to equal
  what the previous stage produces (shared).
- [`expected/`](./expected/): the three grading reports (shared; never
  edit them).
- `starter/{python,typescript}/main.py|ts`: the op engine, the unit layer,
  the trace, and the verdict are complete; the end-to-end runner restarts
  at every stage.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. In `run_pipeline` (`runPipeline` in TypeScript), give the first stage a
   copy of the pipeline's `start` record and give every later stage the
   record the previous stage produced.
2. Leave the components' `unit_case` inputs to the unit layer, where they
   belong. The assembled run reads only `start`, `stages`, and `expects`.
3. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: once the record is threaded,
`file-writer` in `seam-gap` receives `path=exports/quarterly.csv` instead
of its own fixture's absolute path and rejects it, so the run stops with
the seam named and the trace ends in `rejected:`; `name-gap` stops one
stage earlier for its own reason; `seam-closed` is unchanged, because
there the two runners agree.

## Expected outcome

Before your change:

```text
  [FAIL] seam-gap-blocked (python) -- stdout mismatch vs expected/seam-gap.json: diverges at $.e2e.checks[0].detail: 'the assembled run completed but written=/tmp/unit-fixture.csv; the flow expects written=/srv/reports/exports/quarterly.csv' != 'the assembled run stopped at file-writer: path=exports/quarterly.csv does not start with /; path was last written by path-builder'
  [FAIL] name-gap-blocked (python) -- stdout mismatch vs expected/name-gap.json: diverges at $.e2e.checks[0].detail: 'the assembled run completed but written=/tmp/unit-fixture.csv; the flow expects written=/srv/reports/exports/quarterly.csv' != 'the assembled run stopped at path-builder: report is not in the record; no component in this flow wrote report'
  [pass] seam-closed-done (python)
```

Both stages call the flow broken, so the verdict and the exit code already
match; the starter is wrong about what happened, reporting a run that
reached the end and wrote the unit fixture's scratch file. After your
change all three cases match, and:

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
<summary>Hint 1: what the loop carries</summary>

The loop already has a `record` variable that the previous iteration
assigned. The starter throws it away at the top of each iteration by
passing something else to the component. Nothing else in the function
needs to change.

</details>

<details>
<summary>Hint 2: why seam-closed passes either way</summary>

In `workspace-seam-closed`, `selection-ui`'s unit input is the flow's
start record, `path-builder`'s is what `selection-ui` produces, and
`file-writer`'s is what `path-builder` produces. The fixtures were written
from the real flow, so restarting each stage lands on the same values.
That coincidence is the reason this class of mistake survives review: it
is invisible until a seam actually disagrees.

</details>

<details>
<summary>Hint 3: read the trace, not the verdict</summary>

Compare your `trace` against `expected/seam-gap.json`. The correct run has
three entries ending in `rejected:`; a per-stage replay has three entries
that each look plausible on their own. The trace is where the difference
between the two runners is visible even when the verdict agrees.

</details>

## Solution walkthrough

The fix is one argument. The starter hands `run_component` the component's
own `unit_case.input`; the solution hands it `record`, the value the
previous stage returned. Everything downstream, the trace, the last-writer
attribution, the detail string, and the verdict, already reads from that
one thread. The `writers` map is why the failure can name `path-builder`
as well as `file-writer`: it accumulates, per field, the component that
last wrote it, and a run that restarts at every stage still fills it in,
which is how the starter manages to produce an attribution that is right
about the map and wrong about the run.
[Project 05](../../../../projects/project-05-self-verification-and-role-separation/)
makes the same move at project scale, running each feature's verification
command against the assembled application rather than inspecting the
components. Cross-track note: both tracks copy the record at every stage
rather than mutating it, so a stage that rejects reports the record it was
handed, in both languages.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-09-why-end-to-end-testing-changes-results/exercises/exercise-01-assembled-run -->
```text
starter/python: exit 1 (as intended: diverges at $.e2e.checks[0].detail: 'the assembled run completed but written=/tmp/unit-fixture.csv; the flow expects written=/srv/reports/exports/quarterly.csv' != 'the assembled run stopped at file-writer: path=exports/quarterly.csv does not start with /; path was last written by path-builder')
starter/typescript: exit 1 (as intended: diverges at $.e2e.checks[0].detail: 'the assembled run completed but written=/tmp/unit-fixture.csv; the flow expects written=/srv/reports/exports/quarterly.csv' != 'the assembled run stopped at file-writer: path=exports/quarterly.csv does not start with /; path was last written by path-builder')
solution/python: exit 0 (PASS: pass (3 checks))
solution/typescript: exit 0 (PASS: pass (3 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
