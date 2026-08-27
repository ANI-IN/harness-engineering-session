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

First release: the foundation sequence, lectures 01-06 and projects 01-03.
The remaining curriculum (lectures 07-14 on scope control, feature lists,
verification, observability, clean state, loops, and graphs; projects 04-08;
the harness-creator skill) follows the same conventions and lands next.

| Lecture | Teaches | Builds toward |
| --- | --- | --- |
| [01: Why capable agents still fail](lectures/lecture-01-why-capable-agents-still-fail/) | Capability is not reliable execution; failures live in five subsystems | Project 01 |
| [02: What a harness actually is](lectures/lecture-02-what-a-harness-actually-is/) | Instructions, tools, environment, state, feedback, as one system | Project 01 |
| [03: Why the repository must become the system of record](lectures/lecture-03-why-the-repository-must-become-the-system-of-record/) | If it's not in the repo, it doesn't exist for the agent | Project 02 |
| [04: Why one giant instruction file fails](lectures/lecture-04-why-one-giant-instruction-file-fails/) | Map, not manual: progressive disclosure | Project 02 |
| 05: Why long-running tasks lose continuity | Context decay; externalized state across sessions | Project 03 |
| 06: Why initialization needs its own phase | init.sh as a first-class phase | Project 03 |

| Project | You build |
| --- | --- |
| 01: Baseline vs minimal harness | A controlled experiment: the same task with and without a harness |
| 02: Agent-readable workspace | A repository an agent can navigate and resume |
| 03: Multi-session continuity | State files and init scripts that survive session boundaries |

## Quick start

Prerequisites: **Python 3.12** with [uv](https://docs.astral.sh/uv/), and
**Node.js 20 LTS** with pnpm (via corepack, which ships with Node). You only
need the toolchain for the track you choose; `make setup` installs both.

```sh
git clone https://github.com/ANI-IN/harness
cd harness
make setup      # uv sync + pnpm install
make doctor     # confirm toolchain versions match the pins
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
