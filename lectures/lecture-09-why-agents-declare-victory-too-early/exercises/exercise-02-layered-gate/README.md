# Exercise 02: layered-gate

## Objective

Make a termination gate stop at the first failing layer, so that checks
behind a failure are reported as not-reached instead of executed, and the
gate matches all three shared expected reports.

## Why this matters

[Lecture 09](../../README.md)'s demo showed a session skipping its
expensive checks and predicting them green. The gate a session should run
instead has the opposite discipline: cheap and fundamental first, and
nothing beyond a failure. The starter runs every layer "for
completeness", and the trap fixture shows what that buys: a failing test
suite with a fully green system layer printed beneath it. Those green
rows are not evidence, because the flow they describe was exercised over
code the tests already reject; they are exactly the reassurance that
makes a session say "the end-to-end log is there, ship it". Signal you
did not earn is worse than no signal, and it also cost the most to
produce.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Demo](../../README.md#demo) and the demo contract's
  check engine and layer field ([../../code/SPEC.md](../../code/SPEC.md)).
- [Exercise 01](../exercise-01-claim-audit/), the audit that runs after a
  claim; this gate runs before one.

## Provided

- [`SPEC.md`](./SPEC.md): the layer order, the not-reached rule, the
  report shape, and the starter's naive decision (shared).
- [`fixtures/workspaces/workspace-settled`](./fixtures/workspaces/workspace-settled/):
  every layer passes (shared).
- [`fixtures/workspaces/workspace-cracked`](./fixtures/workspaces/workspace-cracked/):
  the trap; the tests layer fails while every system check would pass
  (shared).
- [`fixtures/workspaces/workspace-torn`](./fixtures/workspaces/workspace-torn/):
  the static layer fails; nothing below it should run (shared).
- [`expected/`](./expected/): the three grading reports (shared; never
  edit them).
- `starter/{python,typescript}/main.py|ts`: the engine, the layer
  grouping, and the verdict are complete; every layer still executes.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. Track the first failing layer as the run proceeds (the starter already
   records it for the verdict).
2. Once a layer has failed, stop executing: each check in every later
   layer is reported with status `not-reached` and detail
   `gated by failing layer <layer>`, and the layer's own status is
   `not-reached`.
3. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: gating the system layer in
`workspace-cracked` and both lower layers in `workspace-torn` replaces
their executed rows with not-reached rows, matching the expected
reports; `workspace-settled` never trips the gate and already matched.

## Expected outcome

Before your change:

```text
[FAIL] cracked-stops-at-tests (python) -- stdout mismatch vs expected/cracked.json: diverges at $.layers[2].checks[0].detail: 'config/app.conf has a line starting with export_dir=' != 'gated by failing layer tests'
[FAIL] torn-stops-at-static (python) -- stdout mismatch vs expected/torn.json: diverges at $.layers[1].checks[0].detail: 'tests/unit-export.txt has a line starting with result=pass' != 'gated by failing layer static'
[pass] settled-passes-every-layer (python)
```

A green config check is reported beneath a failing test suite. After
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
<summary>Hint 1: the verdict already knows</summary>

The starter computes `stopped_at` correctly. The fix is to consult it
before executing a layer, not after: a layer that starts with
`stopped_at` set never calls the engine.

</details>

<details>
<summary>Hint 2: two row shapes, one loop</summary>

An executed row is `{id, status: pass|fail, detail: <engine>}`; a gated
row is `{id, status: not-reached, detail: gated by failing layer <name>}`.
Build the gated rows from the layer's declared checks so the ids and
their order stay the same as an executed run would have printed.

</details>

## Solution walkthrough

The solution keeps the starter's loop and adds one branch on
`stopped_at`: before it is set, the layer executes and may set it; after,
the layer is reported as gated. The reference the lecture draws on states
the same rule as prose, "do not proceed to the next level if this one
fails"; this exercise makes it a property the expected output enforces.
Two things follow. The report becomes honest about what it knows, which
is the difference between "the system layer passed" and "the system layer
was not exercised". And cost falls in the right place: the checks that
cost three steps each are the ones a failing cheaper layer excuses you
from running. Cross-track note: the gated detail string embeds the
stopping layer's name, and both tracks capture that name once when the
layer fails rather than recomputing it, so the same string appears on
every gated row.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-09-why-agents-declare-victory-too-early/exercises/exercise-02-layered-gate -->
```text
starter/python: exit 1 (as intended: diverges at $.layers[2].checks[0].detail: 'config/app.conf has a line starting with export_dir=' != 'gated by failing layer tests')
starter/typescript: exit 1 (as intended: diverges at $.layers[2].checks[0].detail: 'config/app.conf has a line starting with export_dir=' != 'gated by failing layer tests')
solution/python: exit 0 (PASS: pass (3 checks))
solution/typescript: exit 0 (PASS: pass (3 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
