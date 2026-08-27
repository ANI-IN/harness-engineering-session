# Exercise 01: init-doctor

## Objective

Fix three naive readiness checks so the doctor separates repositories that
are initialized from repositories that merely look initialized, matching
both shared expected reports.

## Why this matters

[Lecture 06](../../README.md)'s claim is that initialization is a phase
with outputs, and the doctor is how you audit those outputs. The starter's
three mistakes share one shape: accepting a file's existence as proof of
its substance. That is exactly how hollow initialization survives: the
files are all there, and none of them does its job.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Demo](../../README.md#demo) and its check rules
  ([../../code/SPEC.md](../../code/SPEC.md)).
- [Lecture 02's subsystem-auditor](../../../lecture-02-what-a-harness-actually-is/exercises/exercise-01-subsystem-auditor/),
  whose existence-vs-substance lesson this exercise deepens.

## Provided

- [`SPEC.md`](./SPEC.md): the contract and the starter's naive mistakes
  (shared).
- [`fixtures/repos/repo-solid`](./fixtures/repos/repo-solid/): properly
  initialized (shared).
- [`fixtures/repos/repo-hollow`](./fixtures/repos/repo-hollow/): every
  artifact present, none doing its job: an unpinned manifest, a
  non-strict `init.sh`, a progress file with no next step (shared).
- [`expected/solid.json`](./expected/solid.json) and
  [`expected/hollow.json`](./expected/hollow.json): the grading authority
  (shared; never edit them).
- `starter/{python,typescript}/main.py|ts`: all four checks run;
  `verification-command` is correct, the other three stop at existence.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. Fix `dependencies-pinned`: every manifest present needs its runtime
   pin; the evidence string names the pair, the failure names the missing
   pin.
2. Fix `init-script`: `init.sh` must also be executable and enable strict
   mode (`set -euo pipefail`); the failure names the missing property.
3. Fix `progress-artifact`: the progress file must carry a
   `- Next best step:` line.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the substantive checks change the
evidence strings on `repo-solid` and flip `repo-hollow` to not-ready
(exit 1) with three named failures, matching both expected reports.

## Expected outcome

Before your change:

```text
[FAIL] solid (python) -- stdout mismatch vs expected/solid.json: diverges at $.checks[0].detail: 'pyproject.toml' != 'pyproject.toml + .python-version'
[FAIL] hollow (python) -- exit code 0 != expected 1; stderr:
```

The hollow repository is declared ready. After your change both cases
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
<summary>Hint 1: the demo is the reference implementation</summary>

This exercise shares the demo's contract; its SPEC defines every rule and
detail string. Implement to the SPEC, not to the fixtures.

</details>

<details>
<summary>Hint 2: three properties, three failure messages</summary>

`init-script` fails three different ways (missing, not executable, not
strict), each with its own detail. Check them in that order so the first
missing property is the one named.

</details>

## Solution walkthrough

The three fixes are the same move at three depths:

- **A manifest without a pin** installs the right dependencies on the
  wrong interpreter; the pair is the unit of reproducibility.
- **An init script without strict mode** keeps going after its first
  failure, which converts a loud initialization problem into a quiet
  mid-session one, the precise thing the init phase exists to prevent.
- **A progress file without a next step** answers "what happened?" and
  not "what now?", so the next session still opens by guessing.

The doctor's verdict lives in the exit code because that is what
`init.sh` and CI can act on. Cross-track note: the executability check is
`os.access(..., X_OK)` in Python and `accessSync(..., X_OK)` in Node,
one of the few places the tracks touch the OS rather than file contents,
and the conformance runner still holds their reports byte-identical.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-06-why-initialization-needs-its-own-phase/exercises/exercise-01-init-doctor -->
```text
starter/python: exit 1 (as intended: diverges at $.checks[0].detail: 'pyproject.toml' != 'pyproject.toml + .python-version')
starter/typescript: exit 1 (as intended: diverges at $.checks[0].detail: 'pyproject.toml' != 'pyproject.toml + .python-version')
solution/python: exit 0 (PASS: pass (2 checks))
solution/typescript: exit 0 (PASS: pass (2 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
