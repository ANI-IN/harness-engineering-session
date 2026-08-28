# Exercise 01: rollback-edge

## Objective

Make the node at the end of a rollback edge replay its journal in the
order that lets it undo the whole run, so the workspace holds nothing the
run added and the report matches all three shared expected outputs.

## Why this matters

A rollback edge is only worth declaring if the node it leads to can
actually take the workspace back. [Lecture 13](../../README.md)'s demo
shows what happens when the edge is missing: the walk stops with a config
file carrying two conflicting keys and a scratch file nobody owns. This
exercise shows the other way to end up there, with the edge present and
fired. An undo that removes what it can, in whatever order it happens to
read, leaves some of the run's own writes behind and reports the workspace
as partly reverted. The graph did route correctly; the node at the end of
the edge did not finish the job.

The order matters for a reason worth carrying past this exercise. Undo is
safe only from the tip: you may remove what your run put there and nothing
else. A run's later writes sit on top of its earlier ones, so the earlier
ones only become removable once the later ones are gone. That is why the
journal is replayed backwards, and why a line something else added after
the run stops the rollback there rather than deleting through it.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Demo](../../README.md#demo), whose `undo` node performs
  exactly this replay, and the demo contract's journal and node table
  ([../../code/SPEC.md](../../code/SPEC.md)).
- The glossary's [graph](../../../../docs/glossary.md#loop-and-graph-vocabulary) entry, for the
  vocabulary of nodes, edges, shared state, and rollback edges.

## Provided

- [`SPEC.md`](./SPEC.md): the contract, the journal shape, the two
  operation kinds and when each may be reverted, and the starter's naive
  reading (shared).
- [`fixtures/workspaces/workspace-applied`](./fixtures/workspaces/workspace-applied/):
  the workspace as the run left it, with two appended lines on one file
  (shared).
- [`fixtures/workspaces/workspace-touched`](./fixtures/workspaces/workspace-touched/):
  the same shape with one further line added after the run stopped, which
  no rollback may remove (shared).
- [`fixtures/journals/`](./fixtures/journals/): three journals;
  `journal-two-appends.json` is the trap, two appends to one file and
  nothing else (shared).
- [`expected/`](./expected/): the three grading reports (shared; never
  edit them).
- `starter/{python,typescript}/main.py|ts`: both reverting rules, the row
  shape, the residue strings, the verdict, and the exit codes are
  complete; only the replay order is naive.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. Read `revert`. It reverts an append only when the line is currently the
   last line of its file, and a create only when the file still holds
   exactly the lines the run wrote. Both rules are correct; leave them.
2. Change `rollback` so the journal is replayed from its last operation to
   its first, while every row is still reported at its own journal index.
3. Leave `residue_of`, the verdict, and the exit codes as they are.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: an append that sits under a later write
by the same run becomes the last line of its file once that later write is
removed, so it flips from `kept` to `reverted`, its residue line
disappears, and the two cases whose whole journal belongs to the run reach
`restored` and exit 0.

## Expected outcome

Before your change:

```text
[FAIL] partly-reverted-under-a-later-change (python) -- stdout mismatch vs expected/partly-reverted.json: diverges at $.operations[0].outcome: 'kept' != 'reverted'
[FAIL] mixed-journal (python) -- exit code 1 != expected 0; stderr:
[FAIL] two-appends-to-one-file (python) -- exit code 1 != expected 0; stderr:
```

The run's earliest write to each file survives its own rollback. After
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
<summary>Hint 1: the loop is the whole change</summary>

`revert` is called once per operation and is already right. The only thing
that decides the outcome of a journal is which operation it is called on
first, and `rollback` is where that is decided.

</details>

<details>
<summary>Hint 2: keep the rows where they are</summary>

The report lists one row per operation at its own `index`, in journal
order. Reversing the loop must not reverse the report: fill the rows by
index, or reverse a copy of the list and sort the rows back afterwards.

</details>

<details>
<summary>Hint 3: what the touched workspace is telling you</summary>

In `workspace-touched`, `config/app.conf` ends with `owner=platform`,
which the run never wrote. That operation is `kept` under every order, and
it is meant to be: it marks the line where an undo has to stop. The rows
that change are the ones buried under the run's own later writes.

</details>

## Solution walkthrough

The fix reverses the replay and nothing else. The reason it works is that
a journal is a stack, not a queue: each write was made on top of the state
the previous writes produced, so the only write that can be removed
without guessing is the most recent one, and removing it exposes the one
before it. Walking forward asks each write to be removable while the
writes that came after it are still in place, which is true only for the
last file the run touched.

What stays failing after the fix is the interesting part. In
`workspace-touched`, `export_dir=out/reports` sits under `owner=platform`,
a line this run never wrote, so no order of replay can reach it: removing
it would mean deleting through a change the run does not own. The node
reports it as `kept`, names it in `residue`, and exits 1, which is the
honest outcome. A rollback edge does not promise a clean workspace, it
promises that everything reversible is reversed and that what is left is
named. That is the same three-way choice the demo's graph makes at the
router: commit, roll back, or stop somewhere a person can read.

Cross-track note: both tracks read workspace files line by line and split
on `/\r?\n/` in TypeScript, so a CRLF fixture grades identically.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-13-graph-engineering/exercises/exercise-01-rollback-edge -->
```text
starter/python: exit 1 (as intended: diverges at $.operations[0].outcome: 'kept' != 'reverted')
starter/typescript: exit 1 (as intended: diverges at $.operations[0].outcome: 'kept' != 'reverted')
solution/python: exit 0 (PASS: pass (4 checks))
solution/typescript: exit 0 (PASS: pass (4 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
