# Exercise 01: rollback-or-finish

## Objective

Give the exit protocol its third move, so an unverified change the session
created is rolled back instead of declared, and the report matches all
three shared expected outputs.

## Why this matters

[Lecture 12](../../README.md)'s dirty ending leaves a half applied
`src/pdf.txt` behind, and the second session inherits a workspace where a
feature is neither done nor absent. The clean ending removes it. This
exercise is the decision behind that removal, and the decision is not
obvious: the handoff template has a "Broken or unverified" section, so
writing the failure down there feels like the responsible move. It is,
for a change to a file that was already in the workspace. For a file this
session brought into existence, reverting is strictly better: it costs
nothing the workspace had before, and it leaves the next session a state
that is consistent rather than one it has to interpret.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Demo](../../README.md#demo), whose clean exit performs
  exactly one rollback, and the demo contract's check engine
  ([../../code/SPEC.md](../../code/SPEC.md)).
- The glossary's
  [clean state](../../../../docs/glossary.md#working-discipline) entry and
  the library's
  [`clean-state-checklist.md`](../../../../library/templates/clean-state-checklist.md).

## Provided

- [`SPEC.md`](./SPEC.md): the contract, the ending-file shape, the table
  of three moves, and the starter's naive decision (shared).
- [`fixtures/workspaces/workspace-open`](./fixtures/workspaces/workspace-open/):
  one file whose check passes, one draft with no `writer=` line, one
  config with no `index_path=` line (shared).
- [`fixtures/workspaces/workspace-settled`](./fixtures/workspaces/workspace-settled/):
  the same three files with every check passing (shared).
- [`fixtures/endings/`](./fixtures/endings/): two ending files;
  `ending-created-only.json` is the trap, a single edit that was created
  this session and does not pass its check (shared).
- [`expected/`](./expected/): the three grading reports (shared; never
  edit them).
- `starter/{python,typescript}/main.py|ts`: the check engine and the
  report are complete; the decision has two branches.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. Bring `created` into `decide`. It is already read from the ending file
   and already reported on every row; nothing consults it.
2. Return `roll-back` for a failing check on a file this session created,
   and keep `declare` for a failing check on a file it did not.
3. Leave `actual`, `detail`, and the summary counts as they are: the
   engine and the report shape are correct already.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: `src/tags.txt` is created and its check
fails, so its row becomes `roll-back` and the summary shifts one count
from `declare` to `roll_back` in both failing cases; `settled-may-end` was
already matching.

## Expected outcome

Before your change:

```text
[FAIL] mixed-ending (python) -- stdout mismatch vs expected/mixed.json: diverges at $.edits[1].decision: 'declare' != 'roll-back'
[FAIL] created-and-unverified (python) -- stdout mismatch vs expected/created-only.json: diverges at $.edits[0].decision: 'declare' != 'roll-back'
[pass] settled-may-end (python)
```

A change the session created and could not verify is written into the
handoff and left in the tree. After your change all three cases match,
and:

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
<summary>Hint 1: the field that is read and never used</summary>

`created` travels from the ending file into every reported row and stops
there. The starter's `decide` takes one argument; the solution's takes
two. Nothing else about the function changes.

</details>

<details>
<summary>Hint 2: why `declare` is still right sometimes</summary>

Reverting `config/store.conf` would not restore a known state; it would
delete lines that were in the workspace before this session touched the
file. Rollback is available exactly when the session owns everything the
revert would remove, which is what `created: true` means.

</details>

<details>
<summary>Hint 3: what the settled case is telling you</summary>

`settled-may-end` passes under both drafts, so it cannot guide you. The
two drafts differ only on rows whose check fails, which is why the trap
fixture contains one edit and that edit fails.

</details>

## Solution walkthrough

The fix adds a branch, and the branch is a claim about ownership rather
than about correctness. Both a rolled-back edit and a declared edit are
unverified work; what separates them is whether reverting is lossless.
Where it is, the exit protocol takes the workspace back to its last
consistent state and the next session sees a feature that is simply
`not-started`. Where it is not, the change stays and the handoff carries
the failing check with a reproduce command, which is the
[`session-handoff.md`](../../../../library/templates/session-handoff.md)
template's "Broken or unverified" section doing its job. The starter used
that section for both, which is how a half applied change gets a paper
trail instead of a fix. [Project 03](../../../../projects/project-03-multi-session-continuity/)
carries the same decision at project scale, in the handoff its second
session has to work from. Cross-track note: both tracks read workspace
files line by line, and the TypeScript track splits on `/\r?\n/` so a CRLF
fixture would grade identically.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-12-why-every-session-must-leave-a-clean-state/exercises/exercise-01-rollback-or-finish -->
```text
starter/python: exit 1 (as intended: diverges at $.edits[1].decision: 'declare' != 'roll-back')
starter/typescript: exit 1 (as intended: diverges at $.edits[1].decision: 'declare' != 'roll-back')
solution/python: exit 0 (PASS: pass (4 checks))
solution/typescript: exit 0 (PASS: pass (4 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
