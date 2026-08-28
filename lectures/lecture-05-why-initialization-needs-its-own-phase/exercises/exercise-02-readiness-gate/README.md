# Exercise 02: readiness-gate

## Objective

Fix the severity tiering so the gate blocks on blockers, proceeds with
visible advice, and says which through its exit code, matching all three
shared expected reports.

## Why this matters

[Lecture 05](../../README.md) makes initialization a gate, and gates need
proportionality: a missing runtime pin should stop a session; a stale
README should not, but must not vanish either. The tier lives in the exit
code because that is the only part of the verdict `init.sh`, CI, and other
programs can act on. The starter's mistake erases the middle tier, which
in practice trains people to ignore the gate.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- [Exercise 01](../exercise-01-init-doctor/), whose check results this
  gate consumes.

## Provided

- [`SPEC.md`](./SPEC.md): the tiering rule and exit-code contract
  (shared).
- [`fixtures/`](./fixtures/): three check-result sets: `all-pass.json`,
  `blocked.json`, `advice-only.json`, the case that separates the tiers
  (shared).
- [`expected/`](./expected/): the grading authority (shared; never edit).
- `starter/{python,typescript}/main.py|ts`: counting works; every failure
  is treated as a blocker.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file, in `gate`.

1. Blockers failed: verdict `blocked`, exit 1.
2. No blockers but advice failed: verdict `ready-with-advice`, exit 3.
3. Nothing failed: verdict `ready`, exit 0.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the restored middle tier changes the
`advice-only` case's verdict and exit code to the expected values.

## Expected outcome

Before your change:

```text
[FAIL] advice-only (python) -- exit code 1 != expected 3; stderr:
```

A wrong verdict delivered through the exit code, before stdout is even
compared. After your change all three cases match, and:

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
<summary>Hint 1: the fix is the missing branch</summary>

The solution is a three-way conditional in tier order: blockers first,
then advice, then ready. The starter collapsed the first two arms.

</details>

<details>
<summary>Hint 2: why exit 3 and not 2</summary>

Exit 2 is this course's usage-error code everywhere. A verdict must never
be confusable with "you called me wrong", so the advice tier takes the
next free code.

</details>

## Solution walkthrough

A small function carrying a real operations lesson:

- **Tiers exist to keep gates credible.** A gate that blocks on everything
  gets bypassed the first busy week, and then it blocks on nothing. The
  middle tier (proceed, but the report stays visible) is what lets the
  strict tier stay strict.
- **Exit codes are the machine-readable half of a verdict.** The starter's
  report *text* was nearly right; its exit code was wrong, and the exit
  code is the part every caller actually consumes. This is the same
  claim-vs-evidence discipline the course applies everywhere, pointed at a
  gate's own output.

Cross-track note: identical rule, identical exit codes; the runner
compares both, and the `advice-only` fixture is the only thing standing
between the naive version and a green build, which is why it exists.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-05-why-initialization-needs-its-own-phase/exercises/exercise-02-readiness-gate -->
```text
starter/python: exit 1 (as intended: exit code 1 != expected 3; stderr: )
starter/typescript: exit 1 (as intended: exit code 1 != expected 3; stderr: )
solution/python: exit 0 (PASS: pass (3 checks))
solution/typescript: exit 0 (PASS: pass (3 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
