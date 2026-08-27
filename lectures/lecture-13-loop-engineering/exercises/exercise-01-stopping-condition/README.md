# Exercise 01: stopping-condition

## Objective

Build the rule that ends a loop: replay a recorded trace of rounds, decide
at each round whether the loop stops there, and make the report match all
three shared expected outputs.

## Why this matters

[Lecture 13](../../README.md)'s demo changes one thing between two runs,
the signal its stopping condition reads, and the loop either reaches the
goal or halts with two thirds of the work undone. Here you write that
condition yourself, over loops that have already run. The transcripts hold
both signals side by side, and the exercise is choosing which one is
allowed to end the loop, plus the rule that ends a loop when neither signal
ever turns.

The choice looks harmless while the two signals agree, and one of the three
fixtures is a trace where they do: it grades identically under either
reading. That is the shape of this failure. Nothing separates a loop
reading the right signal from one reading the wrong signal until a round
arrives where the maker's step passes its own check on a goal that is still
two criteria short, and by then the loop has already stopped.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Demo](../../README.md#demo), whose two behavioural runs
  differ only in the signal read, and the demo contract's clock and
  stopping condition ([../../code/SPEC.md](../../code/SPEC.md)).
- The glossary's
  [maker/checker split](../../../../docs/glossary.md#working-discipline)
  and its loop vocabulary ([glossary](../../../../docs/glossary.md)).

## Provided

- [`SPEC.md`](./SPEC.md): the contract, the transcript shape, the table of
  four decisions, and the starter's naive reading (shared).
- [`fixtures/transcripts/never-converges.json`](./fixtures/transcripts/never-converges.json):
  the trap, five rounds of a loop whose checker never passes (shared).
- [`fixtures/transcripts/converges.json`](./fixtures/transcripts/converges.json):
  four rounds where the checker passes at round 3 (shared).
- [`fixtures/transcripts/signals-agree.json`](./fixtures/transcripts/signals-agree.json):
  two rounds where both signals turn in the same round (shared).
- [`expected/`](./expected/): the three grading reports (shared; never
  edit them).
- `starter/{python,typescript}/main.py|ts`: the clock, the budget rule, the
  `not-run` tail, and the report are complete; the signal is read from the
  wrong party.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. Change `reached_the_goal` (`reachedTheGoal` in TypeScript) to read the
   round's `checker.verdict` instead of its `maker.reports_done`. A `pass`
   verdict is what ends the loop.
2. Leave the budget rule alone: a round the clock cannot afford is refused
   before it starts, and refusing it does not advance the clock.
3. Leave `unmet_at_stop`, the reason strings, and the verdict mapping as
   they are: they are correct already.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: in `never-converges` the loop runs all
four affordable rounds and the clock refuses round 5, and in `converges`
it stops at round 3 with nothing unmet, which is exit 0 instead of exit 1.
`signals-agree` was already matching.

## Expected outcome

Before your change:

```text
[FAIL] never-converges (python) -- stdout mismatch vs expected/never-converges.json: diverges at $.rounds[0].decision: 'stop-done' != 'continue'
[FAIL] converges-at-round-three (python) -- exit code 1 != expected 0; stderr: 
[pass] signals-agree (python)
```

The loop ends at round 1 on the maker's report, four rounds go `not-run`,
and a trace that reached its goal is reported as `stopped-early`. After
your change all three cases match, and:

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
<summary>Hint 1: the field that is read everywhere except the decision</summary>

`checker.unmet` already reaches the report through `unmet_at_stop`, so the
checker's row is being parsed on every round. `checker.verdict` sits next
to it and nothing reads it. One function changes, and only its return
expression.

</details>

<details>
<summary>Hint 2: why the maker's report is not a smaller version of the checker's</summary>

They answer different questions. `reports_done` is true when the step the
maker just took satisfies its own criterion; the verdict is `pass` only
when every criterion of the goal is met. In `never-converges` round 1 the
first is true and the second is false, and the loop had three more useful
rounds in it.

</details>

<details>
<summary>Hint 3: what the third fixture is telling you</summary>

`signals-agree` passes under both drafts, so it cannot guide you. Its maker
re-checks the whole goal before reporting, which makes the two signals
identical for that trace. A loop reading either signal is correct there and
correct only by luck.

</details>

## Solution walkthrough

The change is one expression, and it is a claim about authority rather than
about accuracy. The maker's report is not wrong: its step really did
satisfy its own criterion, and in `never-converges` round 3 it honestly
reports `not-done` when the step failed. It is simply an answer to a
smaller question than the one the loop is asking, and a stopping condition
that reads it ends the loop as soon as any step succeeds. The checker's
verdict is the same question the loop's goal asks, graded by the party that
did not do the work
([maker/checker split](../../../../docs/glossary.md#working-discipline)).

The budget rule is what remains after that fix, and `never-converges` is
why it is there: with the checker's verdict read correctly, that loop has
no reason to ever stop, so the clock is the only thing that ends it. Both
rules are needed and they answer different failures, which is why the
starter is a partial implementation rather than a wrong one.

Cross-track note: both tracks read the same transcript JSON and emit the
same report, and the conformance runner holds them byte-identical after
normalization.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-13-loop-engineering/exercises/exercise-01-stopping-condition -->
```text
starter/python: exit 1 (as intended: diverges at $.rounds[0].decision: 'stop-done' != 'continue')
starter/typescript: exit 1 (as intended: diverges at $.rounds[0].decision: 'stop-done' != 'continue')
solution/python: exit 0 (PASS: pass (4 checks))
solution/typescript: exit 0 (PASS: pass (4 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
