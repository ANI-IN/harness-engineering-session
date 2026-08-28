# Exercise 01: subsystem-auditor

## Objective

Fix three naive subsystem audits (tools, environment, state) so the auditor
scores six fixture repositories exactly as the shared expected report says.

## Why this matters

[Lecture 02](../../README.md) defines a harness as five subsystems, each
with a minimal artifact. Auditing for those artifacts makes the definition
operational, and makes its language-neutrality concrete: every criterion
you fix checks ordinary files (`AGENTS.md`, `verify.sh`,
`feature_list.json`, manifests, runtime pins). Nothing you audit for is
Python or TypeScript, and both tracks audit the same fixture trees. The
starter's three mistakes are real-world ones: trusting descriptions over
existence, declaring dependencies without pinning the runtime, and keeping
scope without narrative.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Concepts](../../README.md#concepts) section (the five
  subsystems and their minimal artifacts).
- [Lecture 01's exercises](../../../lecture-01-why-capable-agents-still-fail/exercises/exercise-01-failure-triage/)
  for the workflow (starter, verify, expected).

## Provided

- [`SPEC.md`](./SPEC.md): the audit criteria, plus the starter's three
  naive mistakes and the trap repo that exposes each (shared).
- [`fixtures/repos/`](./fixtures/repos/): six repositories to audit
  (shared): `repo-complete` (5/5), `repo-no-state` (working but amnesiac),
  `repo-prompt-only` (a prompt file is not a harness), and three traps
  built for the starter's mistakes: `repo-talks-tools` (instructions
  describe `verify.sh`; the file does not exist), `repo-unpinned` (a
  manifest, no runtime pin), `repo-list-only` (a feature list, no progress
  file).
- [`expected/audit-report.json`](./expected/audit-report.json): the grading
  authority (shared; never edit it).
- `starter/{python,typescript}/main.py|ts`: all five audits run; tools,
  environment, and state are naive first drafts that overcount.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. Fix the tools audit: a mention of `verify.sh` in the instructions is
   not the tool; the file itself must exist.
2. Fix the environment audit: require the runtime pin alongside the
   manifest (Python pair first, then Node pair), and produce the SPEC's
   two-part evidence string.
3. Fix the state audit: require `claude-progress.md` alongside
   `feature_list.json`.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the corrected criteria stop the
overcounting, which fixes the three trap repos' scores (5/5 → 4/5,
4/5 → 3/5, 5/5 → 4/5) and the evidence strings everywhere.

## Expected outcome

Before your change, verification fails on the very first repo, where the
naive environment audit's evidence names only half the criterion:

```text
[FAIL] basic (python) -- stdout mismatch vs expected/audit-report.json: diverges at $.repos[0].subsystems.environment.evidence: 'pyproject.toml' != 'pyproject.toml + .python-version'
```

After your change: `repo-complete` 5/5, `repo-list-only` 4/5 (missing
state), `repo-no-state` 4/5, `repo-prompt-only` 1/5, `repo-talks-tools`
4/5 (missing tools), `repo-unpinned` 3/5 (missing environment and state),
and:

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
<summary>Hint 1: the divergence names the missing half</summary>

The first failure is an evidence string: the naive audit found
`pyproject.toml` where the SPEC's criterion is
`pyproject.toml + .python-version`. Each naive audit is missing exactly
one conjunct; the trap repos in `fixtures/repos/` each make one of those
missing conjuncts change a score.

</details>

<details>
<summary>Hint 2: repo-talks-tools is the tools mistake in miniature</summary>

Its `AGENTS.md` says `- Verification: ./verify.sh`, and there is no
`verify.sh`. Grep-based auditing scores it present; existence-based
auditing scores it absent. Note the feedback audit legitimately stays
present there: the *line* exists, the *tool* does not, and the two audits
measure different subsystems.

</details>

<details>
<summary>Hint 3: overcounting vs undercounting</summary>

The naive audits never miss a healthy repo; they bless unhealthy ones.
When your fix is right, no score goes up; three go down.

</details>

## Solution walkthrough

The three fixes tighten each criterion from "some signal" to the SPEC's
conjunction, and each conjunction exists because the failure mode is
conjunctive:

- **Tools: existence, not mention.** `repo-talks-tools` is lecture 02's
  "describing feedback is not having feedback" note applied to tools. An
  auditor that greps instructions inherits every aspiration the
  instructions contain.
- **Environment: manifest + pin.** A manifest without a runtime pin
  reproduces the dependency tree on the wrong interpreter, the exact
  failure the lecture demo's environment ablation simulates.
- **State: list + progress.** `feature_list.json` says what is done;
  `claude-progress.md` says what happened and what's next. `repo-list-only`
  keeps scope and still loses the narrative across sessions.

The starter's failure mode is deliberately *overcounting*: it produces
wrong values with real evidence strings, not empty results, so every
divergence points at a specific criterion rather than at "not
implemented". Cross-track note: the Python solution uses `pathlib`
predicates; TypeScript uses `node:fs` checks; the criteria are identical
because the artifacts are language-neutral files.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-02-what-a-harness-actually-is/exercises/exercise-01-subsystem-auditor -->
```text
starter/python: exit 1 (as intended: diverges at $.repos[0].subsystems.feedback.evidence: 'Verification line in AGENTS.md' != 'Verification line in AGENTS.md: ./verify.sh')
starter/typescript: exit 1 (as intended: diverges at $.repos[0].subsystems.feedback.evidence: 'Verification line in AGENTS.md' != 'Verification line in AGENTS.md: ./verify.sh')
solution/python: exit 0 (PASS: pass (1 check))
solution/typescript: exit 0 (PASS: pass (1 check))
4/4 acceptance runs performed
```
<!-- /generated-block -->
