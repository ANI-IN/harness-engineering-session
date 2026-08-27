# Exercise 01: claim-audit

## Objective

Fix a claim audit that trusts what a session wrote down, so that every
claimed check is re-executed against the workspace as it is now and the
report matches all three shared expected outputs.

## Why this matters

[Lecture 09](../../README.md)'s claim is that a completion declaration
sticks unless something re-executes its checks. The demo's gate does that
for a claim it derived itself. Real claims arrive as records: a transcript
line, a feature entry with an evidence string, a "tests pass" in a
handoff note. The starter's one mistake is the natural reading of such a
record: the check was executed, the output is right there, so accept it.
The trap fixture shows why that reading fails: a check that was green
when recorded is red now, and an audit that reads the record instead of
the workspace declares the stale claim earned.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Demo](../../README.md#demo) and the demo contract's
  check engine ([../../code/SPEC.md](../../code/SPEC.md)).
- The glossary's [evidence](../../../../docs/glossary.md#working-discipline)
  entry: the recorded command and result that justify a status claim.

## Provided

- [`SPEC.md`](./SPEC.md): the contract, the claim-file shape, and the
  starter's naive decision (shared).
- [`fixtures/workspaces/workspace-drifted`](./fixtures/workspaces/workspace-drifted/):
  a workspace that moved after its session recorded evidence; the unit
  result is now `result=fail` and the end-to-end log never appeared
  (shared).
- [`fixtures/workspaces/workspace-earned`](./fixtures/workspaces/workspace-earned/):
  every check holds (shared).
- [`fixtures/claims/`](./fixtures/claims/): three recorded claims;
  `claim-recorded-green.json` is the trap, four checks recorded as
  executed with the exact detail strings the engine printed when they
  were true (shared).
- [`expected/`](./expected/): the three grading reports (shared; never
  edit them).
- `starter/{python,typescript}/main.py|ts`: the engine and the report are
  complete; executed-basis rows are accepted on their record.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. In the audit loop, re-execute every claimed check through the engine,
   whatever its recorded basis; `actual` and `detail` always come from
   that fresh run.
2. Leave the recorded `evidence` string unused by the report: it is what
   the session believed, and the audit's job is to test that belief.
3. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: re-executing the executed-basis rows
turns the stale unit pass in `stale-evidence` into `actual: fail`,
`verdict: diverged`, and two divergences instead of one, matching the
expected report; the other two cases were already matching.

## Expected outcome

Before your change:

```text
[FAIL] stale-evidence (python) -- stdout mismatch vs expected/stale-evidence.json: diverges at $.reexecution[1].actual: 'pass' != 'fail'
[pass] predictions-caught (python)
[pass] earned-confirmed (python)
```

The stale record is reported as the current state. After your change all
three cases match, and:

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
<summary>Hint 1: one branch too many</summary>

The starter's audit loop has two branches keyed on `basis`. The solution
has one. Nothing about a check's basis changes what the engine should do
with it.

</details>

<details>
<summary>Hint 2: why the other two cases already pass</summary>

In `claim-predictions.json` the stale unit check is predicted, so the
starter re-executes it and finds the failure; in `claim-earned.json`
every recorded pass still holds. A record misleads only when it disagrees
with the workspace, which is precisely the condition an audit exists to
detect and the one the starter cannot see.

</details>

## Solution walkthrough

The fix deletes a distinction. The starter treated the claim's `basis`
field as a reason to skip work; the solution treats it as metadata that
travels into the report unchanged while every row gets the same
treatment: run the probe, compare to the claim, name the verdict. The
recorded evidence strings in the fixtures are byte-for-byte what the
engine printed when they were true, which is the strongest form the trap
can take: the record is not fabricated, only old. [Project 05](../../../../projects/project-05-self-verification-and-role-separation/)'s
`evidence-true` rubric item makes the same move at project scale, re-running
the recorded command inside a sandbox. Cross-track note: both tracks read
the workspace files line by line, and the TypeScript track splits on
`/\r?\n/` so a CRLF fixture would grade identically.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-09-why-agents-declare-victory-too-early/exercises/exercise-01-claim-audit -->
```text
starter/python: exit 1 (as intended: diverges at $.reexecution[1].actual: 'pass' != 'fail')
starter/typescript: exit 1 (as intended: diverges at $.reexecution[1].actual: 'pass' != 'fail')
solution/python: exit 0 (PASS: pass (3 checks))
solution/typescript: exit 0 (PASS: pass (3 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
