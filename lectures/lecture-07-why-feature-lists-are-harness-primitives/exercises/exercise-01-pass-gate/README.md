# Exercise 01: pass-gate

## Objective

Fix the passing branch of a feature-list transition gate so that
`passing` is granted only on evidence from the feature's own verification
command recording a passing run, matching all seven shared expected
verdicts.

## Why this matters

[Lecture 07](../../README.md)'s claim is that a feature list is a
primitive because components execute against it, and this gate is the
component that gives `passing` its meaning. The starter's mistake is the
one the reference material warns about in its pass-gate policy: it
accepts that evidence exists without asking what it is. An agent that
records `echo done` as evidence gets the same verdict as one that ran the
tests, and a recorded failure counts the same as a recorded pass. The
list then says `passing` about work nothing has checked, which is the
memo session's false "done" wearing a schema.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Architecture](../../README.md#architecture) state
  machine and its [Demo](../../README.md#demo).
- The canonical dialect:
  [`feature_list.schema.json`](../../../../library/templates/feature_list.schema.json),
  whose statuses and evidence object this gate enforces at transition
  time.

## Provided

- [`SPEC.md`](./SPEC.md): the transition rules, reason strings, and exit
  codes (shared).
- [`fixtures/lists/`](./fixtures/lists/): two canonical feature lists,
  `fresh` (all `not-started`) and `mid-task` (`auth` passing with
  evidence, `cart` in progress, `payments` blocked, `csv-export` not
  started) (shared).
- [`fixtures/requests/`](./fixtures/requests/): six transition requests,
  including the trap pair `pass-cart-foreign.json` (evidence from
  `echo done`) and `pass-cart-failing.json` (the right command, a recorded
  `exit 1`) (shared).
- [`expected/`](./expected/): the grading authority (shared; never edit).
- `starter/{python,typescript}/main.py|ts`: legal edges, WIP=1, and
  finality are correct; the passing branch accepts any evidence.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file, in the `in-progress` to
`passing` branch of `decide`.

1. Refuse when `evidence.command` differs from the feature's
   `verification`, naming both in the reason.
2. Refuse when `evidence.observed` does not start with `exit 0`, quoting
   the observed result.
3. Allow otherwise, with the reason naming the verification command the
   evidence matched.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: checking the evidence's command and
observed result changes the `pass-cart-verified` reason to the expected
affirmative string and flips `pass-cart-foreign` and `pass-cart-failing`
from allowed (exit 0) to refused (exit 1).

## Expected outcome

Before your change:

```text
[FAIL] pass-cart-verified (python) -- stdout mismatch vs expected/pass-cart-verified.json: diverges at $.reason: 'evidence recorded' != 'evidence matches the verification command (./verify.sh cart)'
[FAIL] pass-cart-foreign (python) -- exit code 0 != expected 1; stderr:
[FAIL] pass-cart-failing (python) -- exit code 0 != expected 1; stderr:
```

The right verdict for the wrong reason, then two features marked passing
on an `echo` and on a recorded failure. After your change all eight cases
match, and:

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
<summary>Hint 1: three questions, in order</summary>

Is there evidence at all? Is its command this feature's `verification`,
byte for byte? Does its observed result begin with `exit 0`? The starter
asks only the first. Each "no" has its own reason string in the SPEC.

</details>

<details>
<summary>Hint 2: the reason is part of the verdict</summary>

`pass-cart-verified` is allowed in both the starter and the solution;
only the reason differs. The reason is what the next session reads to
know why the list says what it says, so an affirmative reason names the
command that was matched, the same way the lecture 05 init doctor's pass
details name the pair they found.

</details>

## Solution walkthrough

The fix is small and the lesson is the module's central one, pointed at
the list's own gate:

- **Evidence is a specific thing.** The schema's `evidence` object has a
  `command` and an `observed` field because a claim of completion is
  only checkable if it says what was run and what happened. The gate
  reads both; presence is not evidence.
- **The command must be the feature's own.** A passing run of something
  else is not a passing run of this feature; matching against
  `verification` is what ties the status to the behavior it claims.
- **Refusals name the gap.** `evidence command 'echo done' does not
  match verification './verify.sh cart'` tells the agent exactly what to
  run next, which is the reason string's job.

Cross-track note: identical rules and reason strings; the runner holds
both tracks to the same eight verdicts, and the two trap requests are
what separate the naive draft from a green build.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-07-why-feature-lists-are-harness-primitives/exercises/exercise-01-pass-gate -->
```text
starter/python: exit 1 (as intended: diverges at $.reason: 'evidence recorded' != 'evidence matches the verification command (./verify.sh cart)')
starter/typescript: exit 1 (as intended: diverges at $.reason: 'evidence recorded' != 'evidence matches the verification command (./verify.sh cart)')
solution/python: exit 0 (PASS: pass (8 checks))
solution/typescript: exit 0 (PASS: pass (8 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
