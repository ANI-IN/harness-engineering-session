# Lecture 04: Why one giant instruction file fails

The natural response to every agent mistake is "add a rule", and the
natural home for every rule is the one file the agent always reads. Follow
that gradient for a few months and you get a long entry file that costs
every task context, buries its own hard constraints, and contradicts
itself. This lecture defends one claim: instructions must be a map, not a
manual, a short entry file routing to topic documents loaded only when a
task needs them.

## Learning objectives

After this lecture and its exercises you can:

- Measure an instruction architecture: per-task signal-to-noise under an
  explicit loading rule, and the zone of every hard constraint.
- Explain why the same rules cost less as a router than as a monolith,
  using numbers a tool computed rather than intuition.
- Keep a router-shaped tree honest with executable checks: entry length,
  resolvable routes, hard constraints in the entry only, no duplicated
  rule text.
- Distinguish instruction signal from topic-word mentions when computing
  relevance.

## Prerequisites

- [Lecture 03](../lecture-03-why-the-repository-must-become-the-system-of-record/):
  the repository as the agent's world; this lecture is about the shape of
  the instructions inside it. [Lecture 02](../lecture-02-what-a-harness-actually-is/)
  for the instructions subsystem.
- A working toolchain (`make setup`, `make doctor`;
  [choosing your track](../../docs/choosing-your-track.md)).
- The glossary's [progressive disclosure](../../docs/glossary.md#working-discipline)
  entry; the entry-file size heuristic lives with the
  [`AGENTS.md`](../../docs/glossary.md#harness-artifacts) definition.

## The problem

You wrote an `AGENTS.md` and it worked, so it grew: style debates, API
history, deploy incident notes, all appended where they would surely be
seen. The observable symptoms arrive gradually. A bug-fix task loads
deploy procedures it will never use. A security rule sits in the middle
third of the file. Two eras of style guidance coexist, and the agent obeys
whichever it read last.

The middle-of-the-file problem is not folklore: Liu et al. measured that
language models use information at the beginning and end of long contexts
substantially better than information in the middle.

> Source: [Lost in the Middle: How Language Models Use Long Contexts (Liu et al., 2023)](https://arxiv.org/abs/2307.03172)

The rest of this lecture's claims are demonstrated by the demo on
committed fixtures, not asserted: the same rules, filed two ways, measured.

## Concepts

- **Map, not manual**: the entry file is a router: what the system is, the
  hard constraints, and where the topic documents are. Depth loads on
  demand ([progressive disclosure](../../docs/glossary.md#working-discipline)).
  The course's working heuristic for entry-file size is roughly 100 lines
  (the split rule matters more than the number).
- **Instruction signal-to-noise (SNR)**: for one task, relevant
  instruction lines over loaded lines. The demo computes it under an
  explicit loading rule; exercise 02 makes you implement the relevance
  half honestly (a line *mentioning* a topic is cost, not signal).
- **Buried hard constraint**: a non-negotiable rule in the middle zone of
  a long file, where recall is weakest. Routers avoid burial structurally:
  the entry stays short, and hard constraints stay in it.
- **Instruction debt**: rules accumulate because adding feels free and
  deleting feels risky, so trees need the same discipline as code: audits,
  deletion, and executable shape checks (exercise 01's validator).
- **This unit's artifacts are language-neutral**, like every instruction
  file in this course: the same fixture trees drive both tracks, and the
  format under measurement is the format this repository's own
  [`AGENTS.md`](../../AGENTS.md) practices, short entry, linked depth.

## Architecture

The mechanism under study is the loading rule: what does a given task pull
into context under each architecture?

```mermaid
flowchart LR
    T["task: fix-login-bug<br/>topics: api, testing"] --> E["entry AGENTS.md<br/>always loaded"]
    T -.-> M["monolith: everything is<br/>in the entry, so everything loads"]
    E --> D1["docs/api.md<br/>loaded: topic matches"]
    E --> D2["docs/testing.md<br/>loaded: topic matches"]
    E -. not loaded .-> D3["docs/deploy.md"]
    E -. not loaded .-> D4["docs/db.md"]
```

Walkthrough: the router's cost for this task is the short entry plus two
matching topic files; the deploy and db documents exist, stay maintained,
and cost nothing here. The monolith's cost for the same task is the whole
file, every time, for every task, which is also what pushes its hard
constraints into the middle zone where they get lost. The demo's
[SPEC.md](./code/SPEC.md) pins the loading rule, the SNR formula, and the
zone/burial rules the diagram summarizes.

## Demo

`code/` contains **instruction-stats**: two fixture trees carry the same
rules, `monolith` (one 45-line file) and `router` (a 15-line entry plus
five topic docs), measured against five tasks. Run it from the repo root:

### Python

```sh
L=lectures/lecture-04-why-one-giant-instruction-file-fails
uv run python $L/code/python/main.py $L/code/fixtures/trees $L/code/fixtures/tasks.json
```

### TypeScript

```sh
L=lectures/lecture-04-why-one-giant-instruction-file-fails
pnpm exec tsx $L/code/typescript/main.ts $L/code/fixtures/trees $L/code/fixtures/tasks.json
```

Both tracks print the same report; the full version (per-task rows and the
hard-constraint inventory) is pinned in
[`code/expected/stats-report.json`](./code/expected/stats-report.json).
The comparison section below is generated from the Python run by
`make verify` (the TypeScript run is held identical by `make conformance`):

<!-- generated-block: uv run python lectures/lecture-04-why-one-giant-instruction-file-fails/code/python/main.py lectures/lecture-04-why-one-giant-instruction-file-fails/code/fixtures/trees lectures/lecture-04-why-one-giant-instruction-file-fails/code/fixtures/tasks.json | uv run python -c "import json,sys; print(json.dumps(json.load(sys.stdin)['comparison'], indent=2))" -->
```json
{
  "mean_snr": {
    "monolith": 0.08444444444444443,
    "router": 0.17071929824561405
  },
  "buried_hard_constraints": {
    "monolith": 1,
    "router": 0
  }
}
```
<!-- /generated-block -->

Interpretation: same rules, same tasks, and the router roughly doubles the
mean fraction of loaded context that is actually for the task, while the
monolith's one security hard constraint sits buried in its middle third
and the router's does not (it lives at the top of a file too short to have
a middle). The measurement is the argument; no percentage in this lecture
was typed by hand.

## Implementation notes

- **Split by escaping the vicious cycle, not by ceremony.** The failure
  loop is: mistake → add a rule to the entry → repeat. The escape is a
  routing question at add-time: which tasks need this rule? If the answer
  names a topic, the rule goes in that topic's document and the entry
  gains at most a route line.
- **The wrong version of the split** is a short entry followed by
  neglect: routes to files that no longer exist, hard constraints leaking
  into topic docs, the same rule filed under two tags. That is why
  exercise 01's validator exists; a shape you do not check is a shape you
  do not have.
- **Position is a budget too.** What must live in the entry goes at its
  top or bottom; the middle of any long file is the weak zone (sourced
  above). Better: keep the entry too short to have a meaningful middle.
- **A real cross-track catch from building this demo**: averaging the
  per-task SNRs diverged between the tracks by one ulp, because Python's
  `sum()` applies Neumaier-compensated summation to floats (3.12+) while
  JavaScript's `reduce` is a naive fold. The conformance gate caught it,
  and the fix was a SPEC rule pinning plain left-to-right accumulation,
  the parity contract working as designed.
- Ecosystem note: instruction trees are markdown in both tracks; only the
  measuring tools differ per language, and they are held to identical
  output.

## Key takeaways

- Instructions are a map, not a manual: short routing entry, topic depth
  on demand, hard constraints where every task will see them.
- Measure, don't argue: SNR under an explicit loading rule and
  hard-constraint zones make architecture quality a computed property.
- "Add a rule" has a routing step; skipping it is how entries balloon.
- A router stays a router only under executable checks: entry length,
  resolvable routes, hard-in-entry, no duplicated rule text.

## Exercises

| Exercise | You build | Difficulty | Time |
| --- | --- | --- | --- |
| [01: router-validator](./exercises/exercise-01-router-validator/) | Three structural checks that keep a router-shaped tree honest | Medium | ~40 min |
| [02: snr-calculator](./exercises/exercise-02-snr-calculator/) | The honest relevance rule behind the SNR metric | Easy | ~20 min |

Both are graded by shared expected output: `./verify.sh --stack=<yours>`
exits 0 when your track's implementation is correct. The related project
for this lecture is
[Project 02: agent-readable workspace](../../projects/project-02-agent-readable-workspace/),
which turns this lecture's mechanism into a working, doctor-checked
workspace.

## Further exploration

- [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172)
- [OpenAI: Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)
- [Anthropic: Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Nielsen Norman Group: Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/),
  the interaction-design principle the router shape borrows
- [Claude Code documentation](https://docs.claude.com/en/docs/claude-code/overview)
  on project instruction files
