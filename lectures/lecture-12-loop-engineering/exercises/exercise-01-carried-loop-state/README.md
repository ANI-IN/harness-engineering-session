# Exercise 01: carried-loop-state

## Objective

Build the memory a loop carries between rounds: read the loop state to see
what has already been attempted, choose the round's criterion from what it
records, write the attempt back before the next round reads it, and make the
report match all three shared expected outputs.

## Why this matters

[Lecture 12](../../README.md) says what iteration adds over a single pass:
state that carries between rounds. Its demo shows the effect from outside,
where round 2 picks a step round 1 did not attempt. Here you build the
mechanism, and you build it on the harder case, a loop that is resumed. Two
of the three fixtures arrive with rounds already behind them, written by
whatever ran them, so the only thing telling this runner where the loop got
to is the file it was handed.

A loop whose memory is off by a single entry does not look broken. It runs,
it takes real steps, it reports honestly on each one. It just spends rounds
on work the loop already did, and it does that inside a budget that was
sized for the work that is left. One of the fixtures makes the cost obvious:
the criterion it re-attempts is `key-declared-once`, so the second edit
appends a duplicate line and turns a criterion that was met into one that is
not.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Demo](../../README.md#demo), whose maker chooses each
  round's step from the rounds recorded in `loop-state.json`, and the demo
  contract's state schema and check engine
  ([../../code/SPEC.md](../../code/SPEC.md)).
- The glossary's loop vocabulary, `Loop` and `Maker-checker loop`
  ([glossary](../../../../docs/glossary.md#loop-and-graph-vocabulary)).
- [Lecture 11](../../../lecture-11-why-every-session-must-leave-a-clean-state/):
  the handoff a session leaves for the next one. A loop state is that
  handoff at every round boundary.

## Provided

- [`SPEC.md`](./SPEC.md): the contract, the state schema, the six steps of a
  round, the three stop reasons, and the starter's naive reading (shared).
- [`fixtures/loop-resumed-blocked/`](./fixtures/loop-resumed-blocked/):
  the trap, a resumed loop with one round left whose state records a
  blocked attempt (shared).
- [`fixtures/loop-resumed-clean/`](./fixtures/loop-resumed-clean/): a
  resumed loop with one round left and both earlier attempts met (shared).
- [`fixtures/loop-fresh-start/`](./fixtures/loop-fresh-start/): a loop with
  an empty memory and four rounds of budget (shared).
- [`expected/`](./expected/): the three grading reports (shared; never edit
  them).
- `starter/{python,typescript}/main.py|ts`: the check engine, the step
  application, the budget rule, the round numbering, the stop reasons, and
  the report are complete; the memory is read one entry short.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. Fix `attempted_criteria` (`attemptedCriteria` in TypeScript) so it
   returns the criterion of every entry in the carried state's `attempted`
   list. Each entry records a round that ran, including one whose
   `outcome` was `unmet`, and `rounds_done` is a count of those entries
   rather than an index into them.
2. Leave `next_criterion` and `record_attempt` alone: choosing the first
   criterion the memory does not name, and appending this round before the
   next one reads it, are correct already.
3. Leave the budget rule, the stop reasons, and the verdict mapping as they
   are.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: in `loop-resumed-blocked` the last round
goes to `export-dir-wired` instead of re-attempting the blocked criterion,
in `loop-resumed-clean` it creates the test case and reaches the goal (exit
0 instead of exit 1), and in `loop-fresh-start` rounds 2 and 3 stop
repeating round 1's step.

## Expected outcome

Before your change:

```text
[FAIL] resumed-blocked-attempt (python) -- stdout mismatch vs expected/resumed-blocked.json: diverges at $.rounds[0].chosen_criterion: 'test-case-present' != 'export-dir-wired'
[FAIL] resumed-one-round-left (python) -- exit code 1 != expected 0; stderr:
[FAIL] fresh-start (python) -- exit code 1 != expected 0; stderr:
[pass] not-a-loop-directory (python)
```

Every run ends with more unmet criteria than it started with a budget for,
and two loops that could reach their goal report `budget-exhausted`. After
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
<summary>Hint 1: compare what the round read with what the state holds</summary>

`memory_read` is in the report on purpose. Run the starter on
`fixtures/loop-resumed-blocked` and put that list next to `attempted` in
`fixtures/loop-resumed-blocked/loop-state.json`. The state has two entries
and the round read one, every round, for the whole run.

</details>

<details>
<summary>Hint 2: a count is not an index</summary>

`rounds_done` is 2 because two rounds ran, and those two rounds are the two
entries in `attempted`. Slicing a list by the number of its own elements
keeps all of them; subtracting one from that number is what drops the most
recent round from the loop's memory.

</details>

<details>
<summary>Hint 3: an attempt that failed is still an attempt</summary>

In `loop-resumed-blocked` the dropped entry has `"outcome": "unmet"`, and
its step cannot ever satisfy its check, which is a defect seeded in that
goal. A loop that forgets attempts because they did not work will retake
exactly the steps that do not work, for as many rounds as its budget
allows.

</details>

## Solution walkthrough

The fix is one slice, and what it restores is the property that separates a
loop from a batch of retries: each round starts from what the last round
left. The three moves are visible in the report. `memory_read` is the read,
`chosen_criterion` is the decision that read supports, and `state_written`
is the write that makes the next round's read correct. Break the read and
the other two still run, which is why the starter looks like a working
runner: it chooses honestly from a memory that is quietly one round stale.

The cost of that staleness is not symmetric with the cost of forgetting
everything. `loop-fresh-start` shows the mild version, a repeated step in a
loop that has budget to spare. `loop-resumed-blocked` shows the version that
matters: the loop is resumed with one round left, the entry the starter
drops is an attempt at a criterion whose step cannot satisfy it, and so the
one remaining round is spent proving that again instead of on the criterion
that was still reachable. The budget is the same in both drafts. Only the
memory changed, and with it what the loop got for its last round.

`loop-resumed-clean` adds the reason a duplicate step is not free. The
criterion is `key-declared-once`, so re-attempting it appends a second
`export_dir=` line and the check reports
`config/app.conf declares export_dir 2 times`. Work the loop had already
finished is undone by the round that repeats it, which is the strongest
argument for writing the state at the end of every round rather than at the
end of the run.

Cross-track note: both tracks read the same loop directory and emit the same
report, and the conformance runner holds them byte-identical after
normalization.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-12-loop-engineering/exercises/exercise-01-carried-loop-state -->
```text
starter/python: exit 1 (as intended: diverges at $.rounds[0].chosen_criterion: 'test-case-present' != 'export-dir-wired')
starter/typescript: exit 1 (as intended: diverges at $.rounds[0].chosen_criterion: 'test-case-present' != 'export-dir-wired')
solution/python: exit 0 (PASS: pass (4 checks))
solution/typescript: exit 0 (PASS: pass (4 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
