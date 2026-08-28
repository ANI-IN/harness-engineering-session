# Exercise 02: completion-gate

## Objective

Fix the evidence rule so the gate refuses a `passing` claim whose feature
declares no verification command at all, matching all four shared
expected reports.

## Why this matters

[Lecture 06](../../README.md)'s under-finish is a feature that looks done
and never ran its verification. The feature list is where that lie is
recorded, as a `passing` status whose evidence does not back it. The
starter already catches the visible frauds: a typecheck filed where the
verification command belongs, and a failing run written down as if it had
passed. What it never asks is whether there was anything to run. A
feature whose `verification` is the empty string satisfies every
comparison in the chain, so the gate's logic is correct and its input is
degenerate, and an unverifiable feature reads as verified. The gate is
where WIP=1 and evidence-based completion meet: nothing starts until the
current thing is finished, and finished means evidence that names a
command.

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
- [`fixtures/`](./fixtures/): four feature lists: `ready.json`,
  `wip-exceeded.json`, `hollow-evidence.json` (a typecheck filed as
  evidence, a recorded failing run, and a claim with no evidence at
  all), and `empty-verification.json`, the trap for this exercise: a
  `passing` feature whose `verification` is the empty string (shared).
- [`expected/`](./expected/): the grading authority (shared; never
  edit).
- `starter/{python,typescript}/main.py|ts`: claim audit, WIP check,
  verdict precedence, and CLI all work, and the evidence rule already
  rejects a missing entry, a different command, and a failing run;
  nothing asks whether a command was declared.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file, in `gate`.

1. Add one branch, ahead of every existing evidence check: a feature
   whose `verification` is empty or whitespace does not back its claim,
   whatever its evidence says. Detail
   `the feature declares no verification command`.
2. Leave the three existing branches and their order alone. The chain is
   first-that-applies, so the new branch has to come first or the
   degenerate input is absorbed by the comparisons below it.
3. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: `empty-verification`'s first claim
currently reports `verified:  reported exit 0` against an expected
`the feature declares no verification command`. That one string is the
whole divergence; `unbacked` already lists both ids.

## Expected outcome

Before your change:

```text
[FAIL] empty-verification (python) -- stdout mismatch vs expected/empty-verification.json: diverges at $.claims[0].detail: 'verified:  reported exit 0' != 'the feature declares no verification command'
```

A feature reported as verified by a command that is the empty string.
After your change all four report cases match, and:

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

No command declared, missing entry, wrong command, failing run, then
verified. The SPEC's table is in that order for a reason: the detail
names the first thing wrong, so a failing run of the wrong command
reports the wrong command. Your branch belongs at the head of that
chain, because every check below it compares against the command, and
comparing against the empty string succeeds.

</details>

<details>
<summary>Hint 2: what `observed` promises</summary>

The schema's evidence records what was run and what was seen. "Seen"
starts with the exit code by convention (`exit 0; 6 assertions
passed`), which is why a prefix test is the whole check; the rest of the
string is for humans.

</details>

## Solution walkthrough

Four checks stand between "a feature is marked passing" and "the claim is
backed", and the one you added is the one that is easy to leave out:

- **There must be a command at all.** This is the empty-input case. Every
  check below compares evidence against `verification`, and an empty
  `verification` makes each comparison succeed: the evidence names the
  same empty command, and the run it records reads as passing. The
  gate's logic was already right; nothing rejected the degenerate input.
  A feature that cannot be verified is not a feature that is verified.
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
the reports byte-for-byte after normalization. `empty-verification` is
the fixture that separates the naive draft from a green build, which is
why both drafts exit 1 on it and the recorded divergence is a value
rather than an exit code.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-06-why-agents-overreach-and-under-finish/exercises/exercise-02-completion-gate -->
```text
starter/python: exit 1 (as intended: diverges at $.claims[0].detail: 'verified:  reported exit 0' != 'the feature declares no verification command')
starter/typescript: exit 1 (as intended: diverges at $.claims[0].detail: 'verified:  reported exit 0' != 'the feature declares no verification command')
solution/python: exit 0 (PASS: pass (5 checks))
solution/typescript: exit 0 (PASS: pass (5 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
