# Exercise 01: failure-triage

## Objective

Implement the three missing attribution rules so the triage tool classifies
a fresh 8-run transcript exactly as the shared expected report says.

## Why this matters

[Lecture 01](../../README.md)'s claim is that failure diagnosis is a rules
job over observable events. Writing the rules yourself, and having a
byte-level expected report grade them, is that claim as practice: no
"looks right", only `verify.sh` exiting 0.

## Prerequisites

- `make setup` completed at the repo root; your track's toolchain green in
  `make doctor` ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Architecture](../../README.md#architecture) section and the
  demo's rules ([../../code/SPEC.md](../../code/SPEC.md)).
- No prior exercises; this is the first in the course.

## Provided

- [`SPEC.md`](./SPEC.md): this unit's contract (shared by both tracks).
- [`fixtures/runs.jsonl`](./fixtures/runs.jsonl): the transcript, 8 runs
  (shared).
- [`expected/triage-report.json`](./expected/triage-report.json): the
  grading authority (shared; never edit it to make verification pass).
- `starter/python/main.py` and `starter/typescript/main.ts`: a working
  triage program with only the instructions and tools rules implemented.
  Everything outside `attribute_event` / `attributeEvent` is complete.
- `solution/{python,typescript}/`: complete implementations to check your
  work against, after you're done.

## Your task

Work only in your track's starter file.

1. In `starter/python/main.py` (or `starter/typescript/main.ts`), find
   `attribute_event` (`attributeEvent`): two rules are implemented, three
   are described in comments.
2. Implement `dependency-or-runtime-missing` (environment): a `shell_error`
   whose detail contains one of the provided environment signals.
3. Implement `repeated-prior-work` (state): any `rework` event.
4. Implement `claim-without-passing-verification` (feedback): a `claim`
   with no earlier passing `verification` in the same run; the earlier
   events are passed to the function.
5. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the three added rule branches change five
runs from `unattributed` to their correct subsystems, which makes your
report byte-identical (after normalization) to `expected/triage-report.json`.

## Expected outcome

Before your change, verification fails with:

```text
[FAIL] basic (python) -- stdout mismatch vs expected/triage-report.json: diverges at $.harness_failure_rate: 0.25 != 0.875
```

After your change, your track prints a report attributing ex-3/ex-4 to
environment, ex-5 to state, ex-6/ex-7 to feedback (ex-8 stays
unattributed), with `"harness_failure_rate": 0.875`, and:

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

The script runs your starter against the shared fixtures and diffs the
normalized output against `expected/` (the same conformance machinery that
grades the whole course). `--target=solution` checks the committed solution
instead.

## Hints

<details>
<summary>Hint 1: where exactly to write code</summary>

Only `attribute_event` / `attributeEvent` needs to change. Each missing rule
is one `if` branch returning the (subsystem, rule-id) pair named in the
comment. Match the existing two branches in style; order matters and the
comments sit exactly where each branch belongs.

</details>

<details>
<summary>Hint 2: the environment rule</summary>

The signal list is already defined above the function
(`ENVIRONMENT_SIGNALS`). The rule fires when the event is a `shell_error`
and any signal appears in `detail` via substring test. Note the tools rule
is checked first, so a `command not found` error can never reach yours.

</details>

<details>
<summary>Hint 3: the feedback rule</summary>

You need the events that happened *before* the claim, which the function
already receives as its second parameter (the starter names it `_prior` in
TypeScript; rename it back to `prior` when you use it). The claim is
unbacked when none of them is a `verification` with result `pass`.

</details>

## Solution walkthrough

The solution adds three branches in SPEC order. Two design points are worth
noticing, because the obvious variations break:

- **Precedence is encoded by branch order, not by data.** In run ex-6, a
  failed verification is followed by an unverified claim; only the claim
  matches a rule, so feedback attribution is correct. But if you check the
  feedback rule before the state rule, a transcript with a rework event
  after an unbacked claim would flip attribution depending on event order
  alone, which SPEC forbids by fixing rule order per event.
- **The feedback rule needs prior events, not global knowledge.** Checking
  "does this run contain a passing verification anywhere" (instead of
  *earlier than the claim*) passes this fixture but is wrong: a
  verification that runs after the claim is exactly the victory-declared-
  too-early pattern. The lecture-02 demo and later exercises reuse this
  distinction.

The two tracks differ only idiomatically: Python's rule uses a generator
with `any(...)` over `prior`; TypeScript uses `Array.prototype.some` with
optional chaining on `result`. The observable behavior is pinned to be
identical by the shared expected report.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-01-why-capable-agents-still-fail/exercises/exercise-01-failure-triage -->
```text
starter/python: exit 1 (as intended: diverges at $.harness_failure_rate: 0.25 != 0.875)
starter/typescript: exit 1 (as intended: diverges at $.harness_failure_rate: 0.25 != 0.875)
solution/python: exit 0 (PASS: pass (1 check))
solution/typescript: exit 0 (PASS: pass (1 check))
4/4 acceptance runs performed
```
<!-- /generated-block -->
