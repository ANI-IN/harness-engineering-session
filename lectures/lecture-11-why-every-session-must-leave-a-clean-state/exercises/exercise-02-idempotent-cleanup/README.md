# Exercise 02: idempotent-cleanup

## Objective

Make the exit protocol's progress step reconcile instead of append, so
re-entering an interrupted cleanup cannot record the same session twice,
and the report matches all three shared expected outputs.

## Why this matters

The exit protocol is the last thing a session runs, which makes it the
thing most likely to be cut off part way: a cancelled run, a crashed
process, a wrapper that runs it again to be sure. A protocol that is only
correct the first time turns that interruption into a second defect,
because the retry now writes a duplicate on top of the mess it was called
to clean. A duplicate progress entry is worse than a missing one: the next
session reads two records of the same session and cannot tell which is
current, which is the exact confusion
[Lecture 11](../../README.md)'s dirty ending produces by a different
route.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Demo](../../README.md#demo), whose clean exit runs the
  same four artifact steps once.
- The glossary's
  [`claude-progress.md`](../../../../docs/glossary.md#harness-artifacts)
  and [`session-handoff.md`](../../../../docs/glossary.md#harness-artifacts)
  entries.

## Provided

- [`SPEC.md`](./SPEC.md): the contract, the four steps with both of their
  outcome strings, and the starter's naive step (shared).
- [`fixtures/workspaces/workspace-dirty`](./fixtures/workspaces/workspace-dirty/):
  a workspace where nothing has been cleaned (shared).
- [`fixtures/workspaces/workspace-half-cleaned`](./fixtures/workspaces/workspace-half-cleaned/):
  the trap, a workspace where the protocol was interrupted after its
  second step, so the session entry and the passing status are already
  written while the scratch file and the handoff are not (shared).
- [`expected/`](./expected/): the three grading reports (shared; never
  edit them).
- `starter/{python,typescript}/main.py|ts`: the pass loop, the report, and
  three of the four steps are complete and already reconcile.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. In `record-progress`, check whether `claude-progress.md` already
   carries a line starting `## Session <id>` before writing anything.
2. When it does, change nothing and return the unchanged outcome
   `claude-progress.md already records session <id>`, with the changed
   flag false so a pass in which nothing else changed reports
   `already-clean`.
3. Leave the insertion path as it is: when the entry is absent it still
   goes in before the first heading that starts `## Session`, with the same
   outcome string.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the trap workspace's first pass and the
clean workspace's second pass both stop writing a duplicate entry, so
`summary.progress_entries` stays 1 and the second pass's verdict becomes
`already-clean`; `dirty-one-pass` was already matching.

## Expected outcome

Before your change:

```text
[pass] dirty-one-pass (python)
[FAIL] half-cleaned-retry (python) -- stdout mismatch vs expected/half-cleaned-retry.json: diverges at $.passes[0].steps[0].outcome: 'added a session 002 entry to claude-progress.md' != 'claude-progress.md already records session 002'
[FAIL] dirty-two-passes (python) -- stdout mismatch vs expected/dirty-two-passes.json: diverges at $.passes[1].steps[0].outcome: 'added a session 002 entry to claude-progress.md' != 'claude-progress.md already records session 002'
```

The retry records session 002 a second time. After your change all three
cases match, and:

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
<summary>Hint 1: the other three steps are the pattern</summary>

`set-statuses` compares each feature's status to the one it wants before
assigning. `clear-scratch` looks for files before deleting. `write-handoff`
reads the handoff's next step before rewriting. Each returns false as its
changed flag when the wanted state is already there. `record-progress` is
the one that acts first and looks never.

</details>

<details>
<summary>Hint 2: what counts as already recorded</summary>

The entry's body may not match byte for byte what this run would write, so
compare on the heading: a line starting `## Session <id>`. The workspace
holds at most one entry per session id, which is what makes the heading a
sufficient key.

</details>

<details>
<summary>Hint 3: why `dirty-one-pass` cannot fail</summary>

Over a workspace nobody has cleaned, appending and reconciling produce the
same file and the same outcome string. That is the shape of this defect:
it is invisible in the only run most protocols are ever tested on.

</details>

## Solution walkthrough

The fix turns one action into a reconciliation, and the report shape
already accounted for it: every step returns a changed flag next to its
outcome, and a pass with no changes is `already-clean`. That flag is what
makes idempotence observable rather than asserted, and `--passes=2` is
what exercises it: the second pass over a cleaned workspace should report
four unchanged steps and touch nothing. The append was not careless. A
progress log genuinely is append-only across sessions; the insight is that
within one session's exit it is a state to converge on, and a retry is the
same session, not a new one. Running the protocol twice is now the
cheapest possible test of it.
[Project 03](../../../../projects/project-03-multi-session-continuity/)
leans on the same property: its session A writes `session-handoff.md` and
its session B, in fresh processes, has to reproduce session A's status
from that file alone. Cross-track note: both
tracks split artifact text on newlines and read every match, and the
TypeScript track splits on `/\r?\n/` so a CRLF fixture would grade
identically.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-11-why-every-session-must-leave-a-clean-state/exercises/exercise-02-idempotent-cleanup -->
```text
starter/python: exit 1 (as intended: diverges at $.passes[0].steps[0].outcome: 'added a session 002 entry to claude-progress.md' != 'claude-progress.md already records session 002')
starter/typescript: exit 1 (as intended: diverges at $.passes[0].steps[0].outcome: 'added a session 002 entry to claude-progress.md' != 'claude-progress.md already records session 002')
solution/python: exit 0 (PASS: pass (4 checks))
solution/typescript: exit 0 (PASS: pass (4 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
