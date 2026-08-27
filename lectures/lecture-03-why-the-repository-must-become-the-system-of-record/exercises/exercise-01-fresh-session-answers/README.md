# Exercise 01: fresh-session-answers

## Objective

Fix three naive extractors so the fresh-session reader answers all five
questions from the right artifacts, exactly as the shared expected reports
say.

## Why this matters

[Lecture 03](../../README.md)'s claim is that the repository is the
agent's entire world, and the fresh-session test is how you measure
whether that world is mapped. The starter's three mistakes are the
real-world ways the test gets faked: answering from the wrong document,
mistaking prose *about* verification for a verification command, and
reading a file's heading instead of its content. Every artifact you
extract from is language-neutral; both tracks read the same bytes.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Demo](../../README.md#demo) section and the demo's
  extraction rules ([../../code/SPEC.md](../../code/SPEC.md)).
- [Lecture 02's exercises](../../../lecture-02-what-a-harness-actually-is/exercises/exercise-01-subsystem-auditor/)
  for the audit mindset this reader mechanizes per-question.

## Provided

- [`SPEC.md`](./SPEC.md): the contract, plus the starter's three naive
  mistakes (shared).
- [`fixtures/repos/repo-atlas`](./fixtures/repos/repo-atlas/): fully
  mapped, and built to trap each naive extractor: prose about verifying
  *before* the real `- Verification:` line, and a progress log that opens
  with a heading (shared).
- [`fixtures/repos/repo-thin`](./fixtures/repos/repo-thin/): two answers
  present, three blanks (shared).
- [`expected/atlas.json`](./expected/atlas.json) and
  [`expected/thin.json`](./expected/thin.json): the grading authority
  (shared; never edit them).
- `starter/{python,typescript}/main.py|ts`: all five extractors run; three
  are naive drafts that return wrong values with real-looking sources.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. Fix `how-organized`: extract the first prose line of
   `docs/ARCHITECTURE.md` (source `docs/ARCHITECTURE.md`), not the
   instructions file's overview.
2. Fix `how-to-verify`: extract the `- Verification:` line's value; a line
   that merely mentions verifying is not a command.
3. Fix `where-are-we`: extract the `- Next best step:` line's value from
   `claude-progress.md`, not the file's heading.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the three corrected extractors change
the answers and sources for questions 2, 4, and 5 on `repo-atlas`, and
flip those questions to unanswered on `repo-thin` (2/5, gap 0.6), matching
both expected reports.

## Expected outcome

Before your change:

```text
[FAIL] atlas (python) -- stdout mismatch vs expected/atlas.json: diverges at $.questions[1].answer: 'atlas-tool: renders local map tiles for offline hiking maps.' != 'Two layers: renderer (tile math, pure) and cache (disk layout under tiles/).'
```

After your change: `repo-atlas` answers 5/5 (gap 0, exit 0) with each
answer from its own artifact, `repo-thin` answers 2/5 (gap 0.6, exit 1),
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
<summary>Hint 1: the solution deletes more than it adds</summary>

The correct extractors reuse the two helpers the starter already has for
the implemented questions (first prose line of a file; a tagged
`- Name: value` line). The naive helpers exist only to make the wrong
drafts run; when you're done, nothing should call them.

</details>

<details>
<summary>Hint 2: why the prose trap matters</summary>

`repo-atlas`'s AGENTS.md says "Always verify your work before claiming
done." two lines above `- Verification: ./verify.sh`. An agent that
"answers" the verify question with exhortation instead of a command has
nothing to execute; the extraction rule wants the command.

</details>

<details>
<summary>Hint 3: repo-thin is the null check</summary>

After your fix, three of repo-thin's questions must come out
`answered: false` with `answer` and `source` null. If any of them still
carries an answer, one of your extractors is still guessing.

</details>

## Solution walkthrough

Each fix replaces a plausible-looking source with the SPEC's exact one,
and each teaches a placement rule from the lecture:

- **Organization lives in the architecture doc**, not the overview line.
  The overview says *what* the system is; only `docs/ARCHITECTURE.md` says
  *how it is arranged*, and answering one question from the other hides a
  blank spot on the map.
- **A command is a contract; prose is not.** The `- Verification:` tagged
  line is extractable, executable, and checkable. The trap line reads
  well and runs nothing, which is exactly the difference between having
  feedback and describing it (lecture 02's point, recurring).
- **Structure beats position.** The progress log's first line is its
  heading; the answer lives on a tagged line. Extractors that rely on
  position break the moment a file gains a title, a comment, or a blank
  line; extractors that rely on structure survive edits.

Cross-track note: both tracks express the tagged-line rule as one anchored
regular expression over the same bytes; Python's `re.MULTILINE` and
JavaScript's `m` flag are the same idea in each idiom.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-03-why-the-repository-must-become-the-system-of-record/exercises/exercise-01-fresh-session-answers -->
```text
starter/python: exit 1 (as intended: diverges at $.questions[1].answer: 'atlas-tool: renders local map tiles for offline hiking maps.' != 'Two layers: renderer (tile math, pure) and cache (disk layout under tiles/).')
starter/typescript: exit 1 (as intended: diverges at $.questions[1].answer: 'atlas-tool: renders local map tiles for offline hiking maps.' != 'Two layers: renderer (tile math, pure) and cache (disk layout under tiles/).')
solution/python: exit 0 (PASS: pass (2 checks))
solution/typescript: exit 0 (PASS: pass (2 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
