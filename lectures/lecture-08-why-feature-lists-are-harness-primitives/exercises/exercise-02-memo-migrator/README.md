# Exercise 02: memo-migrator

## Objective

Fix the status mapping of a memo-to-feature-list migrator so that prose
claims of completion become `in-progress` entries carrying the claim as
an unverified note, never `passing`, matching both shared expected
drafts.

## Why this matters

[Lecture 08](../../README.md)'s demo shows a session ending on a false
"done" because its tracker was a memo. The way out is not to throw the
memo away but to migrate it into the single source of truth, and the
migration is where the discipline is tested: the memo says `auth` is
done, and the naive draft writes `passing`. That is the same false claim
in a stricter file format, and the canonical dialect refuses it (a
`passing` entry needs evidence). The migrator's job is to keep the claim
and strip the promotion, so the next session's first act is to run the
verification command, not to trust the note.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture demo's memo grammar and reading rule
  ([../../code/SPEC.md](../../code/SPEC.md)); this exercise reuses both.
- [Exercise 01](../exercise-01-pass-gate/), the gate that will later
  decide whether the migrated `in-progress` entries earn `passing`.

## Provided

- [`SPEC.md`](./SPEC.md): the migration rules and exit codes (shared).
- [`fixtures/scope.json`](./fixtures/scope.json): the authoritative
  scope, four features with behaviors and verification commands (shared).
- [`fixtures/notes-fresh.md`](./fixtures/notes-fresh.md),
  [`fixtures/notes-midway.md`](./fixtures/notes-midway.md) (the trap: two
  claims, one remaining, one unmentioned), and
  [`fixtures/notes-unknown.md`](./fixtures/notes-unknown.md) (a mention
  outside the scope) (shared).
- [`expected/`](./expected/): the grading authority (shared; never edit).
- `starter/{python,typescript}/main.py|ts`: parsing, scope authority, and
  the unknown-feature conflict work; claims are written as `passing`.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file, in the status mapping inside
`migrate`.

1. A claimed feature (a mention without `need` or `todo`) becomes
   `in-progress`, with `notes` set to
   `unverified claim from notes.md: "<prose>"`.
2. Remaining and unmentioned features stay `not-started` with no notes.
3. No entry is ever `passing`.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: mapping claims to `in-progress`
changes the two claimed entries' `status` in the `migrate-midway` draft
to the expected values.

## Expected outcome

Before your change:

```text
[FAIL] migrate-midway (python) -- stdout mismatch vs expected/midway.json: diverges at $.features[0].status: 'passing' != 'in-progress'
```

A prose claim promoted to the one status the dialect reserves for
evidence. After your change all four cases match, and:

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
<summary>Hint 1: which status means "claimed, unverified"</summary>

The dialect has four statuses. `passing` is for evidence, `not-started`
says nothing was done, `blocked` names a dependency. Work that exists but
has not passed its command is the remaining one.

</details>

<details>
<summary>Hint 2: the note is the memo's only surviving contribution</summary>

The starter already writes the note; keep it. The claim is useful
information for the next session (run this command first), as long as it
sits in `notes` and not in `status`.

</details>

## Solution walkthrough

Three rules, one principle:

- **Scope comes from one file.** The scope file supplies every entry's
  identity, behavior, and verification command, in its order. A memo
  mention outside it is a conflict (exit 1), not a new feature; scope
  that arrives through prose is exactly what a single source of truth
  forbids.
- **Claims are recorded as claims.** `in-progress` plus a note preserves
  what the previous session believed while making the list say only what
  is proven. The draft validates against the canonical schema, which a
  draft with `passing` and no evidence would not.
- **The migrated list creates immediate work.** Two `in-progress` entries
  exceed WIP=1, which is the correct pressure: the next session's first
  job is to run `./verify.sh auth` and `./verify.sh cart` and let
  exercise 01's gate promote or hold each one.

Cross-track note: identical memo grammar and reading rule in both tracks,
shared with the lecture demo; the runner compares the full drafts, so an
extra or missing `notes` key fails as loudly as a wrong status.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-08-why-feature-lists-are-harness-primitives/exercises/exercise-02-memo-migrator -->
```text
starter/python: exit 1 (as intended: diverges at $.features[0].status: 'passing' != 'in-progress')
starter/typescript: exit 1 (as intended: diverges at $.features[0].status: 'passing' != 'in-progress')
solution/python: exit 0 (PASS: pass (4 checks))
solution/typescript: exit 0 (PASS: pass (4 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
