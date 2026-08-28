# Exercise 02: completion-gate

## Objective

Fix the evidence rule so the gate backs a `passing` claim only with a
recorded passing run of the feature's own verification command, matching
all three shared expected reports.

## Why this matters

[Lecture 06](../../README.md)'s under-finish is a feature that looks done
and never ran its verification. The feature list is where that lie is
recorded, as a `passing` status with hollow evidence: a typecheck filed
where the verification command belongs, or a failing run written down
as if it had passed. The starter accepts both, which means it would let a
session activate the next feature on top of two unverified ones. The gate
is where WIP=1 and evidence-based completion meet: nothing starts until
the current thing is finished, and finished means evidence.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- [Exercise 01](../exercise-01-scope-auditor/), the other half of the
  boundary (what a session may touch; this exercise is what it may
  claim).
- The glossary's [evidence](../../../../docs/glossary.md#working-discipline)
  entry and the library's
  [`feature_list.schema.json`](../../../../library/templates/feature_list.schema.json),
  whose evidence shape the fixtures use.

## Provided

- [`SPEC.md`](./SPEC.md): the evidence rule, the WIP rule, the verdict
  precedence, and the seeded defects (shared).
- [`fixtures/`](./fixtures/): three feature lists: `ready.json`,
  `wip-exceeded.json`, and `hollow-evidence.json`, the trap with a
  typecheck as evidence, a recorded failing run, and a claim with no
  evidence at all (shared).
- [`expected/`](./expected/): the grading authority (shared; never
  edit).
- `starter/{python,typescript}/main.py|ts`: claim audit, WIP check,
  verdict precedence, and CLI all work; any recorded evidence entry
  counts as proof.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file, in `gate`.

1. Evidence whose `command` is not the feature's `verification` does not
   back the claim: detail
   `evidence names a different command (<got>, not <verification>)`.
2. Evidence whose `observed` does not start with `exit 0` does not back
   the claim: detail `evidence records a failing run (<observed>)`.
3. Only evidence that passes both checks is `verified: <verification>
   reported exit 0`; a missing entry stays `no evidence recorded`.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the two new checks change the details
of the typecheck claim and the failing-run claim in `hollow-evidence` to
the expected strings, which also lengthens `unbacked` to the expected
three ids.

## Expected outcome

Before your change:

```text
[FAIL] hollow-evidence (python) -- stdout mismatch vs expected/hollow-evidence.json: diverges at $.claims[1].detail: 'verified: ./verify.sh --feature delete-endpoint reported exit 0' != 'evidence names a different command (npx tsc --noEmit, not ./verify.sh --feature delete-endpoint)'
```

A claim declared verified by a command that never ran. After your change
all three cases match, and:

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
<summary>Hint 1: the rule is a chain of first-that-applies checks</summary>

Missing entry, wrong command, failing run, then verified. The SPEC's
table is in that order for a reason: the detail names the first thing
wrong, so a failing run of the wrong command reports the wrong command.

</details>

<details>
<summary>Hint 2: what `observed` promises</summary>

The schema's evidence records what was run and what was seen. "Seen"
starts with the exit code by convention (`exit 0; 6 assertions
passed`), which is why a prefix test is the whole check; the rest of the
string is for humans.

</details>

## Solution walkthrough

Three checks stand between "an evidence entry exists" and "the claim is
backed":

- **The command must be the feature's own verification command.** A
  typecheck that exits 0 proves the code compiles, not that the behavior
  passes, which is the substitution the lecture warned about ("the code
  looks fine" filed as evidence).
- **The run must have passed.** Recording a failing run is honest
  bookkeeping and still not completion; the gate names the observed
  result so the next session knows what to re-run.
- **Precedence keeps the verdict readable.** `wip-exceeded` outranks
  `unbacked-claims` because two features in flight means no single claim
  is even the right question yet; `may_activate` is true only when the
  verdict is `sound` and nothing is in progress, the WIP=1 discipline
  as a boolean.

Cross-track note: the `hollow-evidence` fixture's `test-layout` entry has
no `evidence` key at all, so Python's `.get` and TypeScript's `??` both
resolve it to the same "no evidence recorded" branch; the runner compares
the reports byte-for-byte after normalization, and this fixture is the
only thing standing between the naive version and a green build, which
is why it exists.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-06-why-agents-overreach-and-under-finish/exercises/exercise-02-completion-gate -->
```text
starter/python: exit 1 (as intended: diverges at $.claims[1].detail: 'verified: ./verify.sh --feature delete-endpoint reported exit 0' != 'evidence names a different command (npx tsc --noEmit, not ./verify.sh --feature delete-endpoint)')
starter/typescript: exit 1 (as intended: diverges at $.claims[1].detail: 'verified: ./verify.sh --feature delete-endpoint reported exit 0' != 'evidence names a different command (npx tsc --noEmit, not ./verify.sh --feature delete-endpoint)')
solution/python: exit 0 (PASS: pass (4 checks))
solution/typescript: exit 0 (PASS: pass (4 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
