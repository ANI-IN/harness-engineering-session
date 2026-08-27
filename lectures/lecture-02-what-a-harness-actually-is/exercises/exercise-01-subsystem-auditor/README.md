# Exercise 01: subsystem-auditor

## Objective

Implement the tools, environment, and state audits so the auditor scores
three fixture repositories exactly as the shared expected report says.

## Why this matters

[Lecture 02](../../README.md) defines a harness as five subsystems, each
with a minimal artifact. Auditing for those artifacts makes the definition
operational, and makes its language-neutrality concrete: every criterion
you implement checks ordinary files (`AGENTS.md`, `verify.sh`,
`feature_list.json`, manifests, runtime pins). Nothing you audit for is
Python or TypeScript, and both tracks audit the same fixture trees.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Concepts](../../README.md#concepts) section (the five
  subsystems and their minimal artifacts).
- [Lecture 01's exercises](../../../lecture-01-why-capable-agents-still-fail/exercises/exercise-01-failure-triage/)
  for the workflow (starter, verify, expected).

## Provided

- [`SPEC.md`](./SPEC.md): the audit criteria, one per subsystem (shared).
- [`fixtures/repos/`](./fixtures/repos/): three repositories to audit
  (shared): `repo-complete` (a full minimal harness), `repo-no-state`
  (working but amnesiac), `repo-prompt-only` (a prompt file and nothing
  else, the "a prompt file is not a harness" case).
- [`expected/audit-report.json`](./expected/audit-report.json): the grading
  authority (shared; never edit it).
- `starter/{python,typescript}/main.py|ts`: the instructions and feedback
  audits implemented; tools, environment, and state report absent.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. Implement the tools audit: present when `verify.sh` exists.
2. Implement the environment audit: present when a manifest and a runtime
   pin coexist; check the Python pair first, then the Node pair, and build
   the evidence string the SPEC names.
3. Implement the state audit: present only when both `feature_list.json`
   and `claude-progress.md` exist.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the three implemented audits change
`repo-complete` to 5/5 and `repo-no-state` to 4/5, which makes your report
byte-identical (after normalization) to the expected report.

## Expected outcome

Before your change:

```text
[FAIL] basic (python) -- stdout mismatch vs expected/audit-report.json: diverges at $.repos[0].missing: length 3 != 0
```

After your change: `repo-complete` 5/5, `repo-no-state` 4/5 (missing
state), `repo-prompt-only` 1/5, and:

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
<summary>Hint 1: all three audits are file-existence checks</summary>

Each audit is a few lines: test whether specific files exist under the repo
path and return the finding with the SPEC's exact evidence string. The two
implemented audits show the pattern, including the helper that nulls
evidence when absent.

</details>

<details>
<summary>Hint 2: the environment audit's pair logic</summary>

Both files of a pair must exist; a manifest alone proves dependencies are
declared but not that the runtime is pinned. Order matters only for the
evidence string when a repo has both pairs; the SPEC says Python pair
first.

</details>

<details>
<summary>Hint 3: why repo-no-state has 4/5, not 4.5</summary>

State requires both files. `repo-no-state` has neither, but even one of
the two would still score absent; partial state is what breaks sessions.

</details>

## Solution walkthrough

The audits are deliberately conjunctive where the failure mode is
conjunctive:

- **State requires both files** because each covers the other's blind spot:
  `feature_list.json` says what is done, `claude-progress.md` says what
  happened and what's next. A repo with only one loses either scope or
  narrative across sessions.
- **Environment requires manifest + pin** because a manifest without a
  runtime pin reproduces the dependency tree on the wrong interpreter, the
  exact failure the lecture demo's environment ablation simulates.
- **`repo-prompt-only` scoring 1/5** is the exercise's thesis: prose
  instructions alone leave four subsystems absent, however good the prose.

Cross-track note: the Python solution uses `pathlib` predicates and a dict
of audit functions; TypeScript uses `node:fs` checks and a typed record of
auditors. The criteria they implement are identical because the artifacts
they check are language-neutral files, which is the lecture's claim in
executable form.
