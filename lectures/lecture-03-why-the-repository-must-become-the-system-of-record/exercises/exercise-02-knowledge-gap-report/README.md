# Exercise 02: knowledge-gap-report

## Objective

Fix the visibility rule so the gap report counts exactly the decisions an
agent can see, matching the shared expected reports for two inventories.

## Why this matters

[Lecture 03](../../README.md) defines the knowledge visibility gap: the
fraction of what the team knows that lives where the agent cannot see it.
Measuring it is how externalization becomes a plan instead of a vibe, and
the starter's mistake is the measurement's classic failure: counting
knowledge as visible because its *name* sounds repository-ish, when only
its *location* decides.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Concepts](../../README.md#concepts) section (knowledge
  visibility gap, system of record).
- [Exercise 01](../exercise-01-fresh-session-answers/), which measures the
  same blindness from the agent's side.

## Provided

- [`SPEC.md`](./SPEC.md): the visibility rule, report shape, and verdict
  threshold (shared).
- [`fixtures/inventory.jsonl`](./fixtures/inventory.jsonl): ten decisions,
  four outside the repo, two of them critical, including the two traps
  whose locations mention "repo" without being in one (shared).
- [`fixtures/inventory-clean.jsonl`](./fixtures/inventory-clean.jsonl): a
  well-externalized project at the 10% boundary (shared).
- [`expected/gap-report.json`](./expected/gap-report.json) and
  [`expected/gap-report-clean.json`](./expected/gap-report-clean.json):
  the grading authority (shared; never edit them).
- `starter/{python,typescript}/main.py|ts`: the report plumbing works;
  `in_repo` is a naive substring test.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file, in `in_repo` / `inRepo`.

1. Replace the substring test with the SPEC's rule: a decision is in-repo
   exactly when its location starts with the prefix `repo:`.
2. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the exact-prefix rule reclassifies the
two trap entries as outside, which corrects the counts (6/4, gap 0.4) and
restores `k-versioning` to `critical_outside`.

## Expected outcome

Before your change:

```text
[FAIL] scattered (python) -- stdout mismatch vs expected/gap-report.json: diverges at $.critical_outside: length 1 != 2
```

A critical decision (the API versioning rule, recorded only in Confluence)
has silently vanished from the outside list. After your change: total 10,
in_repo 6, outside 4, gap 0.4, `critical_outside` carrying both critical
ids, verdict `needs-externalization`, and:

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

Both inventories are checked; the clean one pins the 0.1 boundary counting
as `acceptable`.

## Hints

<details>
<summary>Hint 1: the fix is one expression</summary>

The rule is a prefix test on `location`. Both languages have a direct
string method for it; no parsing is needed.

</details>

<details>
<summary>Hint 2: why the clean inventory already passes</summary>

The starter's naive rule only misfires on locations that mention "repo"
without the `repo:` prefix. The clean inventory has none, so it passes
before your fix: a reminder that a rule can look correct on friendly data
and still be wrong.

</details>

## Solution walkthrough

The one-line fix carries the lecture's sharpest distinction:

- **Location, not vocabulary.** "Confluence: repo guidelines page" is
  knowledge *about* the repository stored *outside* it; the agent cannot
  read Confluence. The naive substring rule encodes the comfortable
  assumption that repository-sounding knowledge is repository-visible,
  and the trap entries are priced to make that assumption cost a critical
  decision.
- **The dangerous error was silent.** The naive rule's headline numbers
  (8/2, gap 0.2) still look plausible; what disappeared was
  `k-versioning` in `critical_outside`, the exact list a team would use to
  prioritize externalization. Measurement bugs that shrink the worry list
  are the ones worth designing fixtures against.

Cross-track note: Python's `location.startswith("repo:")` and
TypeScript's `location.startsWith("repo:")` differ by one letter of
casing; the shared expected reports hold both to the same bytes.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-03-why-the-repository-must-become-the-system-of-record/exercises/exercise-02-knowledge-gap-report -->
```text
starter/python: exit 1 (as intended: diverges at $.critical_outside: length 1 != 2)
starter/typescript: exit 1 (as intended: diverges at $.critical_outside: length 1 != 2)
solution/python: exit 0 (PASS: pass (2 checks))
solution/typescript: exit 0 (PASS: pass (2 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
