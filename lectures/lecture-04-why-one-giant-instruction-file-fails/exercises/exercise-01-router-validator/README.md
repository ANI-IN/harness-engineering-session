# Exercise 01: router-validator

## Objective

Fix three naive structural checks so the validator holds a router-style
instruction tree to lecture 04's rules, matching the shared expected
reports for a clean tree and a broken one.

## Why this matters

[Lecture 04](../../README.md) argues for the router shape; this exercise
is about *keeping* it. Split instruction trees rot in specific ways
(routes go dead, hard constraints leak into topic docs, rules get
duplicated under new tags), and each of those ways defeats the shape's
purpose silently. The validator turns the shape into executable rules, the
same move the course makes with every convention it cares about.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Concepts](../../README.md#concepts) and the demo's
  instruction format ([../../code/SPEC.md](../../code/SPEC.md)).
- [Lecture 02's subsystem-auditor](../../../lecture-02-what-a-harness-actually-is/exercises/exercise-01-subsystem-auditor/),
  whose per-check report shape this validator reuses.

## Provided

- [`SPEC.md`](./SPEC.md): the four checks and the starter's three naive
  mistakes (shared).
- [`fixtures/trees/tree-good`](./fixtures/trees/tree-good/): a clean
  router (shared).
- [`fixtures/trees/tree-broken`](./fixtures/trees/tree-broken/): three
  seeded violations, one per naive mistake (shared).
- [`expected/tree-good.json`](./expected/tree-good.json) and
  [`expected/tree-broken.json`](./expected/tree-broken.json): the grading
  authority (shared; never edit them).
- `starter/{python,typescript}/main.py|ts`: all four checks run;
  `entry-length` is correct, the other three are naive first drafts.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. Fix `routes-resolve`: a route line violates when its target file does
   not exist in the tree; parsing the line is not resolving it.
2. Fix `hard-in-entry`: scan the topic docs, not the entry; a hard
   constraint is a violation exactly when it appears *outside*
   `AGENTS.md`.
3. Fix `no-duplicates`: compare rule **text** (the part after the topic
   tag), so a duplicate cannot hide behind a different tag.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the corrected checks stop flagging the
legitimate entry constraint on `tree-good` and start catching all three
seeded violations on `tree-broken`, matching both expected reports.

## Expected outcome

Before your change, verification fails first on the *clean* tree:

```text
[FAIL] tree-good (python) -- stdout mismatch vs expected/tree-good.json: diverges at $.checks[2].passed: False != True
```

The naive hard-constraint check reports a violation in the one place hard
constraints belong. After your change: `tree-good` passes all four checks
(`ok: true`), `tree-broken` fails `routes-resolve`, `hard-in-entry`, and
`no-duplicates` with one located violation each (`ok: false`), and:

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
<summary>Hint 1: why the starter fails on the clean tree first</summary>

The naive `hard-in-entry` inverted its own scan: it kept only `AGENTS.md`
and flagged what it found there. The fix is the one-character kind: scan
everything *except* the entry. Read the check's name as its contract.

</details>

<details>
<summary>Hint 2: resolving a route</summary>

The route regex already extracts the target path. Resolution means asking
the filesystem whether `tree/<target>` exists, exactly as the solution's
other checks ask about files.

</details>

<details>
<summary>Hint 3: what counts as "the same rule"</summary>

`- [api] Use pagination cursors, never offsets.` and
`- [style] Use pagination cursors, never offsets.` are one rule filed
twice. The rule text is the match group after the tag; compare that.

</details>

## Solution walkthrough

Each fix converts a check from testing an *artifact of the rule* to
testing the rule:

- **Routes resolve** is lecture 03's dead-link lesson turned inward: a
  routing line pointing at a missing doc sends the agent to a blank spot
  while looking well-maintained. Existence, not syntax, is the contract.
- **Hard constraints live in the entry** because that is the file every
  task loads; a hard constraint in `docs/db.md` is only seen by tasks that
  route there, which is how "never" rules become "usually" rules. The
  naive version's inversion (flagging the entry) is the instructive bug:
  it enforced the letter of "find hard constraints" while reversing the
  policy.
- **Duplicates by text** because the topic tag is metadata; the demo's SNR
  metric already showed that every duplicated line is loaded noise for
  most tasks, and drift between two copies is worse than the noise.

Cross-track note: both solutions keep the four checks as a declarative
list of (id, function) pairs, so adding a fifth check is data, not
plumbing; Python uses tuples, TypeScript a typed array.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-04-why-one-giant-instruction-file-fails/exercises/exercise-01-router-validator -->
```text
starter/python: exit 1 (as intended: diverges at $.checks[2].passed: False != True)
starter/typescript: exit 1 (as intended: diverges at $.checks[2].passed: False != True)
solution/python: exit 0 (PASS: pass (2 checks))
solution/typescript: exit 0 (PASS: pass (2 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
