# Learn Harness Engineering

A project-based course on **harness engineering**: the discipline of building
the execution system around an AI coding agent (instructions, tools,
environment, state, and feedback) so that a capable model becomes a reliable
worker. You will read short, mechanism-focused lectures, build each mechanism
yourself in verifiable exercises, and compose them into working projects.

Everything in this repository runs **offline**, in **two complete language
tracks**, Python and TypeScript, against one shared specification. You pick
a track; you never need the other one to learn.

## Why this course exists

Strong models still fail at multi-step engineering work, not because they
lack capability, but because they work inside weak systems: no durable state
between sessions, no executable definition of "done", instructions buried in
one giant file, no feedback the agent can actually read. Harness engineering
fixes the system instead of waiting for a bigger model. The primary sources
this course builds on:

- [OpenAI: Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)
- [Anthropic: Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Anthropic: Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)

## How the course is organized

Six parts, one learning flow:

1. **Lectures**: one defended claim each, with a runnable demo in both tracks.
2. **Exercises**: per lecture, modify starter code until `verify.sh` exits 0.
3. **Solutions**: committed, idiomatic, passing implementations of every exercise, in both tracks.
4. **Projects**: compose the mechanisms of two lectures into a working system.
5. **Skills**: the course's workflows packaged for coding agents (ships with the full curriculum).
6. **Library**: the copy-ready harness templates, single-sourced for the whole repo.

The flow for each topic: **read the lecture, do its exercises, build the
project, keep the templates.** The [curriculum map](docs/curriculum-map.md)
draws how everything connects.

## Curriculum

The tables below list everything the course currently contains; every row
links to a unit that runs today.

| Lecture | Teaches | Builds toward |
| --- | --- | --- |
| [01: Why capable agents still fail](lectures/lecture-01-why-capable-agents-still-fail/) | Capability is not reliable execution; failures live in five subsystems | [Project 01](projects/project-01-baseline-vs-minimal-harness/) |
| [02: What a harness actually is](lectures/lecture-02-what-a-harness-actually-is/) | Instructions, tools, environment, state, feedback, as one system | [Project 01](projects/project-01-baseline-vs-minimal-harness/) |
| [03: Why the repository must become the system of record](lectures/lecture-03-why-the-repository-must-become-the-system-of-record/) | If it's not in the repo, it doesn't exist for the agent | [Project 02](projects/project-02-agent-readable-workspace/) |
| [04: Why one giant instruction file fails](lectures/lecture-04-why-one-giant-instruction-file-fails/) | Map, not manual: progressive disclosure | [Project 02](projects/project-02-agent-readable-workspace/) |
| [05: Why long-running tasks lose continuity](lectures/lecture-05-why-long-running-tasks-lose-continuity/) | Context decay; externalized state across sessions | [Project 03](projects/project-03-multi-session-continuity/) |
| [06: Why initialization needs its own phase](lectures/lecture-06-why-initialization-needs-its-own-phase/) | init.sh as a first-class phase | [Project 03](projects/project-03-multi-session-continuity/) |
| [07: Why agents overreach and under-finish](lectures/lecture-07-why-agents-overreach-and-under-finish/) | WIP=1 read from the workspace; a parked queue instead of a refusal | [Project 04](projects/project-04-runtime-feedback-and-scope-control/) |
| [08: Why feature lists are harness primitives](lectures/lecture-08-why-feature-lists-are-harness-primitives/) | The triple (behavior, command, status); passing only through the command | [Project 04](projects/project-04-runtime-feedback-and-scope-control/) |
| [09: Why agents declare victory too early](lectures/lecture-09-why-agents-declare-victory-too-early/) | Re-execution, not review, separates an earned claim from a premature one | [Project 05](projects/project-05-self-verification-and-role-separation/) |
| [10: Why end-to-end testing changes results](lectures/lecture-10-why-end-to-end-testing-changes-results/) | The definition of done decides the result: seams are only exercised assembled | [Project 05](projects/project-05-self-verification-and-role-separation/) |
| [11: Why observability belongs inside the harness](lectures/lecture-11-why-observability-belongs-inside-the-harness/) | The harness records what the session did, so the next session can repair rather than guess | Closest: [Project 04](projects/project-04-runtime-feedback-and-scope-control/) |

| Project | You build |
| --- | --- |
| [01: Baseline vs minimal harness](projects/project-01-baseline-vs-minimal-harness/) | A controlled experiment: the same task with and without a harness |
| [02: Agent-readable workspace](projects/project-02-agent-readable-workspace/) | A repository an agent can navigate and resume |
| [03: Multi-session continuity](projects/project-03-multi-session-continuity/) | State files and init scripts that survive session boundaries |
| [04: Runtime feedback and scope control](projects/project-04-runtime-feedback-and-scope-control/) | Structured logs, corrupt-state recovery, an executable architecture guard, and WIP=1 |
| [05: Self-verification and role separation](projects/project-05-self-verification-and-role-separation/) | Maker, checker, and planner roles graded by a rubric of executable predicates |

## Quick start

Prerequisites: **Python 3.12** with [uv](https://docs.astral.sh/uv/), and
**Node.js 20 LTS** with pnpm (via corepack, which ships with Node). You only
need the toolchain for the track you choose, plus Python and uv either
way (they power the verification machinery; see
[choosing your track](docs/choosing-your-track.md)).

```sh
git clone https://github.com/ANI-IN/harness
cd harness
make setup TRACK=python   # or TRACK=typescript, or plain `make setup` for both
make doctor TRACK=python  # confirm exactly what your track requires
make verify     # run everything - should be green on a fresh clone
```

Then pick your track ([choosing your track](docs/choosing-your-track.md)
covers setup, differences, and what is shared) and start with lecture 01.

## Repository structure

```text
docs/           conventions, glossary, curriculum map, track chooser
lectures/       lecture-NN-<slug>/ - README, runnable demo (code/), exercises/
projects/       project-NN-<slug>/ - README, SPEC, starter/, solution/, tests
library/        copy-ready harness templates (single source of truth)
tools/          conformance runner + structure/link/mermaid/prose linters
```

Every runnable unit has one shape (shared `SPEC.md`, `fixtures/`,
`expected/`, plus `python/` and `typescript/` implementations) and one
verification contract. [docs/conventions.md](docs/conventions.md) is the
standard every folder follows.

## Verification and the parity contract

This course practices what it teaches: every claim of "working" is backed by
an executable check.

```sh
make verify           # every unit's verify.sh (both stacks) + all test suites
make conformance      # python vs typescript vs expected/ - must be identical
make lint             # ruff + eslint + markdownlint + shellcheck + prose rules
make lint-links       # every relative link + anchor resolves
make lint-mermaid     # every diagram parses
make lint-structure   # every unit complete, every README in required order
```

The two tracks must produce identical observable output for the same input:
same stdout, same exit codes, same written files, measured after the defined
normalization pass. Divergence fails the build. CI runs the full set on every
push (Python 3.12 × Node 20).

## Troubleshooting

- **`make doctor` reports a pin mismatch**: install the pinned versions.
  Python 3.12 comes from `uv sync` automatically; Node 20 via your version
  manager (`.nvmrc` is present); pnpm activates with `corepack enable pnpm`.
- **pnpm not found after installing Node**: corepack ships with Node but
  starts disabled. Run `corepack enable pnpm` once.
- **A unit's `verify.sh` fails on a fresh clone**: that is a bug in this
  repository, not your setup. Please open an issue with the output.

## Contributing, security, support

- [CONTRIBUTING.md](CONTRIBUTING.md): how changes are made and verified here.
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md): expected behavior in this project's spaces.
- [SECURITY.md](SECURITY.md): reporting security issues.
- Questions and bug reports: [GitHub issues](https://github.com/ANI-IN/harness/issues).

## Acknowledgments and license

Modeled on the public reference course
[walkinglabs/learn-harness-engineering](https://github.com/walkinglabs/learn-harness-engineering):
same curriculum structure and concepts, with all content written fresh,
every exercise made verifiable, and full dual-stack parity. Licensed under the
[MIT License](LICENSE).
