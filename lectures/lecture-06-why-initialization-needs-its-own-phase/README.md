# Lecture 06: Why initialization needs its own phase

A session that starts by improvising its environment ends by guessing
about its work. This lecture defends one claim: initialization is a phase
of its own, with its own outputs (a runnable environment, a working
verification path, recorded state, a committed baseline), and mixing it
into feature work shortchanges both.

## Learning objectives

After this lecture and its exercises you can:

- Name the outputs an initialization phase owes the sessions after it, and
  audit a repository for them mechanically.
- Distinguish artifacts that exist from artifacts that do their job (a
  pinned environment vs a manifest; a strict init script vs a file named
  `init.sh`).
- Build a readiness gate whose verdict is machine-consumable, with
  blockers and advice tiered through exit codes.
- Explain the single-file `init.sh` exception to this course's dual-track
  rules and why it exists.

## Prerequisites

- [Lecture 05](../lecture-05-why-long-running-tasks-lose-continuity/):
  the continuity artifacts initialization must leave behind;
  [Lecture 02](../lecture-02-what-a-harness-actually-is/) for the
  environment subsystem.
- A working toolchain (`make setup`, `make doctor`;
  [choosing your track](../../docs/choosing-your-track.md)).
- The library's [`init.sh` template](../../library/templates/init.sh).

## The problem

You open a session and say "add the search feature." The agent starts
eagerly, then discovers mid-task that the test runner was never
configured, fixes that, then hits a dependency mismatch, fixes that, and
finally writes some feature code with whatever context budget is left.
The next session inherits none of the fixes' reasoning and re-derives the
project from scratch. Anthropic's write-up on long-running agents reaches
the same design conclusion this lecture teaches: their two-part harness
begins with "an initializer agent that sets up the environment on the
first run", separate from the coding agent that does feature work.

> Source: [Anthropic: Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

## Concepts

- **Initialization is a phase, not a chore list.** Its outputs are
  infrastructure: dependencies installed *and pinned*, a verification
  command that runs, state files that answer where-are-we, a clean
  baseline. Feature code is explicitly not among them.
- **Two different optimization targets.** Implementation maximizes
  verified features now; initialization maximizes the reliability of
  every session after it. An agent asked to do both at once favors the
  visible one, which is how infrastructure ends up hollow.
- **Existence is not readiness.** The demo's broken fixture has an
  `init.sh`, a manifest, and instructions, and still cannot host a
  session: the script isn't strict, the interpreter isn't pinned, the
  progress file doesn't exist. Readiness checks must test substance.
- **The startup gate**: run the doctor at session start (from `init.sh`
  or by hand); blockers stop the session before it wastes budget, advice
  stays visible without stopping it (exercise 02's tier rule).
- **`init.sh` is the declared single-file exception** to this course's
  two-track presentation (see
  [conventions](../../docs/conventions.md#command-blocks)): initialization
  is one language-neutral artifact, so one script shows both ecosystems'
  install paths side by side, guarded by manifest checks, instead of
  existing twice. The demo's ready fixture carries a live instance.

## Architecture

Initialization is a lifecycle stage with entry and exit conditions, so the
diagram is a state machine:

```mermaid
stateDiagram-v2
    [*] --> Initializing: session starts
    Initializing --> Ready: doctor passes (exit 0)
    Initializing --> Blocked: blocker fails (exit 1)
    Blocked --> Initializing: fix what the report names
    Ready --> Working: feature work begins
    Working --> HandedOff: state recorded, clean baseline
    HandedOff --> [*]
```

Walkthrough: `Initializing` is the phase this lecture separates out; its
only exits are a passing doctor or a named blocker, so a session cannot
drift into `Working` with an unpinned interpreter or an unrecorded state
file. The `Blocked` loop is cheap precisely because the doctor's report
names what to fix. `Working` and `HandedOff` are lectures 07-12 territory;
the state machine shows why they depend on this phase: every later stage
assumes the invariants `Ready` certifies. The demo's
[SPEC.md](./code/SPEC.md) pins the four checks behind that `Ready` edge.

## Demo

`code/` contains **init-check**: the startup-readiness doctor, run against
`repo-ready` (fully initialized, including the dual-ecosystem `init.sh`)
and `repo-broken` (three seeded gaps). Run it from the repo root:

### Python

```sh
L=lectures/lecture-06-why-initialization-needs-its-own-phase
uv run python $L/code/python/main.py $L/code/fixtures/repos/repo-broken
```

### TypeScript

```sh
L=lectures/lecture-06-why-initialization-needs-its-own-phase
pnpm exec tsx $L/code/typescript/main.ts $L/code/fixtures/repos/repo-broken
```

Both tracks print the same report and exit 1 (initialization still owes
this repository something). The block below is generated from the Python
run by `make verify` (the TypeScript run is held identical by
`make conformance`):

<!-- generated-block: uv run python lectures/lecture-06-why-initialization-needs-its-own-phase/code/python/main.py lectures/lecture-06-why-initialization-needs-its-own-phase/code/fixtures/repos/repo-broken || true -->
```json
{
  "checks": [
    {
      "id": "dependencies-pinned",
      "passed": false,
      "detail": "package.json present but .nvmrc missing"
    },
    {
      "id": "init-script",
      "passed": false,
      "detail": "init.sh does not enable strict mode (set -euo pipefail)"
    },
    {
      "id": "verification-command",
      "passed": true,
      "detail": "AGENTS.md: ./verify.sh"
    },
    {
      "id": "progress-artifact",
      "passed": false,
      "detail": "claude-progress.md missing"
    }
  ],
  "ready": false
}
```
<!-- /generated-block -->

Interpretation: three failures, each naming its exact gap (the missing
pin, the missing strict mode, the missing progress file), and one passing
check, because a broken repo is rarely broken everywhere and a doctor
must report per-check. Against `repo-ready` the same command reports four
passes and exit 0; that report is pinned in
[`code/expected/ready.json`](./code/expected/ready.json), and the
fixture's [`init.sh`](./code/fixtures/repos/repo-ready/init.sh) is the
single-file dual-ecosystem exception, labeled as such in its header.

## Implementation notes

- **Give the first session an initialization-only goal.** Its definition
  of done is the doctor passing plus a committed baseline, not a feature.
  The library's [`init.sh` template](../../library/templates/init.sh) is
  the artifact it should leave behind.
- **The wrong version of initialization** is the checklist in prose:
  "make sure tests run" ages into untruth the first week nobody re-runs
  it. The doctor is the checklist as a program, and wiring it into
  `init.sh` means it re-runs every session start by construction.
- **Strict mode is the difference between loud and quiet failure.** An
  init script without `set -euo pipefail` keeps going past its first
  error and hands the session a half-built environment with a green
  banner. The doctor checks for it because the failure mode it prevents
  is invisible by definition.
- **Record decisions made during initialization** (test framework,
  layout, dependency choices) in the progress file's decision lines;
  lecture 05's simulator showed what re-deciding costs.
- Track note: everything the doctor inspects is language-neutral, and the
  environment check is deliberately dual-ecosystem: it validates
  whichever manifest pairs exist, which is also how this repository's own
  `make doctor` treats its two toolchains.

## Key takeaways

- Initialization has outputs; if a session cannot name them, it is not
  initializing, it is stalling feature work with setup debris.
- Audit substance, not existence: pinned pairs, strict executable
  scripts, progress files with a next step.
- Gate the start of work on the doctor's exit code, with blockers and
  advice tiered so the gate stays credible.
- One `init.sh` serves both ecosystems by design; that exception is
  declared once and labeled where it lives.

## Exercises

| Exercise | You build | Difficulty | Time |
| --- | --- | --- | --- |
| [01: init-doctor](./exercises/exercise-01-init-doctor/) | The three substance checks behind the readiness doctor | Medium | ~35 min |
| [02: readiness-gate](./exercises/exercise-02-readiness-gate/) | The severity tiering that keeps the gate credible | Easy | ~20 min |

Both are graded by shared expected output: `./verify.sh --stack=<yours>`
exits 0 when your track's implementation is correct. The related project
for this lecture is Project 03 (multi-session continuity), which lands
with the projects phase of this course.

## Further exploration

- [Anthropic: Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [OpenAI: Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)
- [The Twelve-Factor App](https://12factor.net/), build/release/run
  separation as the same phase discipline for services
- [Claude Code documentation](https://docs.claude.com/en/docs/claude-code/overview)
