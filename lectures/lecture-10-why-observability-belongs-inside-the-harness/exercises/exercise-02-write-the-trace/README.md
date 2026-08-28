# Exercise 02: write-the-trace

## Objective

Fix a harness logger that records the wrong prior value, so that each
`workspace/write` event names the value that write actually replaced and
the report matches both shared expected outputs.

## Why this matters

[Lecture 10](../../README.md)'s resume session works because one field in
one event holds a value the workspace no longer contains. That field has
to be filled by the harness at the moment of the write, and there are two
plausible places to read it from: the file on disk, or the state the
session is holding. The starter picks the file, which is the reading that
feels most concrete and is wrong the instant a session writes the same
key twice. The result is the worst kind of log: present, well formed,
parseable, consumed without complaint, and quietly useless. A downstream
audit still attributes, still proposes a repair, and proposes restoring
the value the failing check already rejects.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Demo](../../README.md#demo) and the demo contract's
  event shape ([../../code/SPEC.md](../../code/SPEC.md)).
- [Exercise 01](../exercise-01-trace-attribution/) is the consumer this
  exercise feeds; its attribution rule is given here, complete.

## Provided

- [`SPEC.md`](./SPEC.md): the contract, the event table, and the
  starter's naive decision (shared).
- [`fixtures/workspaces/workspace-ingest`](./fixtures/workspaces/workspace-ingest/):
  the trap. Its plan writes `chunk_size` at step 2 and overwrites it at
  step 4 (shared).
- [`fixtures/workspaces/workspace-clean`](./fixtures/workspaces/workspace-clean/):
  the control. Its plan writes every key at most once, so the value on
  disk and the value the session holds are the same value (shared).
- [`expected/`](./expected/): the two grading reports (shared; never edit
  them).
- `starter/{python,typescript}/main.py|ts`: the overlay, the check
  engine, and the whole consumer half (attribution and repair plan) are
  complete; only the logger's `from` is wrong.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. In the session loop, take the `from` value from the session's own
   overlay rather than by re-reading the file from disk.
2. Read it before the overlay write lands, not after.
3. Change nothing in the consumer half: the attribution rule and the
   repair strings are already correct and are graded as they stand.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: reading the overlay makes event 5
record `from: "512"`, the value step 4 destroyed, instead of `"0"`, the
value the file had before the session started; the consumer then proposes
`restore chunk_size=512` and `overwrite-recorded` matches. The control
case was already matching.

## Expected outcome

Before your change:

```text
[FAIL] overwrite-recorded (python) -- stdout mismatch vs expected/overwrite-recorded.json: diverges at $.events[4].detail.from: '0' != '512'
[pass] single-writes-agree (python)
[pass] missing-workspace (python)
```

Event 5 claims the value went from 0 to 0, which is a write that changed
nothing, over the step that broke the workspace. After your change both
report cases match, and:

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
<summary>Hint 1: where the session's writes actually go</summary>

Nothing in this program touches the filesystem after startup. Every write
lands in the `Overlay`, and the overlay loads a file from disk once, on
first touch. So a disk read after step 2 returns what the file held
before step 2 ran.

</details>

<details>
<summary>Hint 2: the accessor already exists</summary>

The overlay exposes a getter that returns a key's current value, and the
line directly below the one you are changing already calls the matching
setter on the same overlay. Order matters: read, then set.

</details>

<details>
<summary>Hint 3: why the clean workspace cannot tell you</summary>

In `workspace-clean` no key is written twice, so the value on disk and
the value in the overlay never diverge and both loggers emit the same
seven events. A test set where every key is touched once will pass a
logger that can never report an overwrite, which is exactly the case
worth logging.

</details>

## Solution walkthrough

One line moves the read from the filesystem to the session's own state,
and the event stops describing the file's past and starts describing the
write. The framing worth keeping is the failure mode: the starter does
not crash, does not warn, and does not produce a malformed log. It
produces a log that a consumer parses happily and reasons from wrongly,
which is why the acceptance signal here is a value inside a well-formed
event rather than an error. The same discipline shows up in
[project 04](../../../../projects/project-04-runtime-feedback-and-scope-control/),
where the log's per-event fields are pinned in its SPEC and its tests
assert the sequence rule directly, not just that logging happened.
Cross-track note: both tracks buffer writes in an in-memory overlay and
never modify the committed fixtures; the TypeScript track splits input on
`/\r?\n/` per the conventions' line-ending rule.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-10-why-observability-belongs-inside-the-harness/exercises/exercise-02-write-the-trace -->
```text
starter/python: exit 1 (as intended: diverges at $.events[4].detail.from: '0' != '512')
starter/typescript: exit 1 (as intended: diverges at $.events[4].detail.from: '0' != '512')
solution/python: exit 0 (PASS: pass (3 checks))
solution/typescript: exit 0 (PASS: pass (3 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
