# Projects

Projects are where the course's mechanisms stop being demos and become a
system. Each project composes what two lectures taught into something that
runs, is tested, and is verified the same way in both language tracks.

All projects share one evolving application: **`kb`**, a local knowledge-base
tool (CLI + small local HTTP server) that imports documents, indexes them,
and answers questions from them with citations. It uses only the standard
library plus the test runner, stores everything in local JSON files, and
replaces model calls with a deterministic fake agent, so every project runs
offline, headless, and reproducibly. Each project's README documents the seam
where a real agent plugs in.

## How a project works

Every `project-NN-<slug>/` directory contains a README (overview through
troubleshooting, in the standard order), the shared `SPEC.md` contract,
language-neutral harness artifacts in `harness/`, shared `fixtures/` and
`expected/`, a genuine `starter/` and a complete `solution/` in both tracks,
and a conformance test suite. The solution runs from a fresh clone with the
documented commands; that is verified, not assumed.

## First-pass curriculum (projects 01-03)

| # | Project | You build | Composes lectures |
| --- | --- | --- | --- |
| 01 | [Baseline vs minimal harness](./project-01-baseline-vs-minimal-harness/) | A controlled experiment: the same build task executed prompt-only vs rules-first, with measured results | 01, 02 |
| 02 | [Agent-readable workspace](./project-02-agent-readable-workspace/) | A repository structured so an agent can navigate it and pick up where the last session left off | 03, 04 |
| 03 | [Multi-session continuity](./project-03-multi-session-continuity/) | State files and an init script that keep work moving across session restarts | 05, 06 |

## Second pass (in progress)

| # | Project | You build | Composes lectures |
| --- | --- | --- | --- |
| 04 | [Runtime feedback and scope control](./project-04-runtime-feedback-and-scope-control/) | Structured logs, corrupt-state recovery, the behavioral architecture guard, and the WIP=1 doctor | 02, 04 |

This index lists every project the course currently contains.
