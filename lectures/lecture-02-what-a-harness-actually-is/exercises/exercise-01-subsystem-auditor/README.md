# Exercise 01: subsystem-auditor

## Objective

Fix two naive subsystem audits (tools and feedback) so the auditor scores
seven fixture repositories exactly as the shared expected report says.

## Why this matters

[Lecture 02](../../README.md) defines a harness as five subsystems, each
with a minimal artifact. Auditing for those artifacts makes the definition
operational, and makes its language-neutrality concrete: every criterion
you fix checks ordinary files (`AGENTS.md`, `verify.sh`,
`feature_list.json`, manifests, runtime pins). Nothing you audit for is
Python or TypeScript, and both tracks audit the same fixture trees. The
starter's two mistakes are real-world ones: trusting that instructions
which *mention* a tool mean the tool exists, and trusting that a tag
which *names* a verification command means a command is there to run.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Concepts](../../README.md#concepts) section (the five
  subsystems and their minimal artifacts).
- [Lecture 01's exercises](../../../lecture-01-why-capable-agents-still-fail/exercises/exercise-01-failure-triage/)
  for the workflow (starter, verify, expected).

## Provided

- [`SPEC.md`](./SPEC.md): the audit criteria, plus the starter's two
  naive mistakes and the trap repo that exposes each (shared).
- [`fixtures/repos/`](./fixtures/repos/): seven repositories to audit
  (shared): `repo-complete` (5/5), `repo-no-state` (working but amnesiac),
  `repo-prompt-only` (a prompt file is not a harness), `repo-unpinned` (a
  manifest, no runtime pin), `repo-list-only` (a feature list, no progress
  file), and the two traps built for the starter's mistakes:
  `repo-talks-tools` (instructions describe `verify.sh`; the file does not
  exist) and `repo-empty-verification` (a `- Verification:` line that
  names nothing after the colon).
- [`expected/audit-report.json`](./expected/audit-report.json): the grading
  authority (shared; never edit it).
- `starter/{python,typescript}/main.py|ts`: all five audits run; the
  environment, state and instructions audits are already correct, and
  tools and feedback are naive first drafts.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. Fix the tools audit: a mention of `verify.sh` in the instructions is
   not the tool; the file itself must exist. Evidence becomes plain
   `verify.sh`.
2. Fix the feedback audit: a `- Verification:` line is the tag, not the
   fact. Read what follows the colon, require it to be non-empty, and
   report the command you found, so the evidence names something a
   reader can run: `Verification line in <file>: <command>`.
3. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the corrected tools audit takes
`repo-talks-tools` from 5/5 to 4/5 and stops crediting a mention in every
other repo's evidence string; the corrected feedback audit takes
`repo-empty-verification` from crediting feedback to naming it missing,
and appends the command to the evidence everywhere it is real.

## Expected outcome

Before your change, verification fails on the very first repo, where the
naive feedback audit's evidence stops at the tag:

```text
[FAIL] basic (python) -- stdout mismatch vs expected/audit-report.json: diverges at $.repos[0].subsystems.feedback.evidence: 'Verification line in AGENTS.md' != 'Verification line in AGENTS.md: ./verify.sh'
```

After your change: `repo-complete` 5/5, `repo-empty-verification` 4/5
(missing feedback), `repo-list-only` 4/5 (missing state), `repo-no-state`
4/5, `repo-prompt-only` 1/5, `repo-talks-tools` 4/5 (missing tools),
`repo-unpinned` 3/5 (missing environment and state), and:

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

The first failure is an evidence string: the naive audit reported
`Verification line in AGENTS.md` where the SPEC's evidence is
`Verification line in AGENTS.md: ./verify.sh`. Each naive audit stops one
step short of its criterion; the two trap repos in `fixtures/repos/` each
make one of those missing steps change a score.

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
<summary>Hint 3: which way each mistake errs</summary>

The naive feedback audit blesses an unhealthy repo, and the naive tools
audit does both: it credits a mention in `repo-talks-tools` that is not
a tool, and it misses the real `verify.sh` in `repo-empty-verification`,
whose instructions never spell the filename. When your fix is right,
`repo-talks-tools` goes down and `repo-empty-verification` trades a
wrongly-credited feedback for a correctly-credited tools.

</details>

## Solution walkthrough

Both fixes replace a proxy with the thing itself, and both proxies are
what a real auditor reaches for first because they are cheaper to read:

- **Tools: existence, not mention.** `repo-talks-tools` is lecture 02's
  "describing feedback is not having feedback" note applied to tools. An
  auditor that greps instructions inherits every aspiration the
  instructions contain, and misses every tool the instructions forgot to
  name.
- **Feedback: the command, not the tag.** A line can carry
  `- Verification:` and name nothing after it, and a subsystem whose
  command is the empty string cannot tell anyone whether the work
  passed. This is the malformed-line case: the shape is right and the
  content is absent. Reporting the command you found is what makes the
  evidence checkable rather than a claim that a check exists.

The environment and state audits are already correct in the starter, and
their conjunctive criteria are worth reading anyway: a manifest without a
runtime pin reproduces the dependency tree on the wrong interpreter, and
`feature_list.json` without `claude-progress.md` keeps scope while losing
the narrative across sessions. `repo-unpinned` and `repo-list-only` pin
both, so a regression there fails the build.

The starter produces wrong values with real evidence strings, not empty
results, so every divergence points at a specific criterion rather than
at "not implemented". Cross-track note: the Python solution uses
`pathlib` predicates; TypeScript uses `node:fs` checks; the criteria are
identical because the artifacts are language-neutral files.

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
