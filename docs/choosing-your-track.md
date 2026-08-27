# Choosing your track

This course is fully dual-stack: every lecture demo, every exercise, and every
project exists in **Python** and in **TypeScript**, implementing the same
shared contract (`SPEC.md`) against the same fixtures and expected outputs.
Pick the language you work in; you will never need to read the other track to
understand a concept.

## What is shared, what is per-track

Harness artifacts are language-neutral by design; that is itself one of the
first lessons of the course. Written once, used by both tracks:

- all prose: lectures, exercise briefs, project docs, diagrams;
- all harness templates: `AGENTS.md`, `CLAUDE.md`, `feature_list.json` (and
  its schema), `init.sh`, `claude-progress.md`, `session-handoff.md`,
  `clean-state-checklist.md`, `evaluator-rubric.md`, `quality-document.md`;
- all test inputs (`fixtures/`) and expected outputs (`expected/`): the same
  files grade both tracks;
- every `verify.sh`.

Only the implementation source differs, and each side is written idiomatically:
dataclasses, `pathlib`, and type hints in Python; discriminated unions,
`readonly`, and strict mode in TypeScript. The two tracks must produce
identical observable behavior; `make conformance` enforces it.

## Setup

Both tracks are installed from the repo root with one command:

```sh
make setup
```

That runs both package managers. If you only want one track, the underlying
commands are:

### Python

Requires **Python 3.12** and [uv](https://docs.astral.sh/uv/). uv installs the
pinned interpreter for you:

```sh
uv sync          # creates .venv with Python 3.12 + pytest + ruff
uv run pytest    # run any Python tests
```

### TypeScript

Requires **Node.js 20 LTS** (see `.nvmrc`) and pnpm via
[corepack](https://nodejs.org/api/corepack.html), which ships with Node:

```sh
corepack enable pnpm
pnpm install
pnpm test        # run any TypeScript tests
```

## Running any unit

Every runnable unit has the same shape and the same entry pattern:

### Python

```sh
uv run python <unit>/python/main.py <args>
./<unit>/verify.sh --stack=python
```

### TypeScript

```sh
pnpm exec tsx <unit>/typescript/main.ts <args>
./<unit>/verify.sh --stack=typescript
```

`verify.sh --stack=both` (the default) checks both tracks, useful if you want
to see the parity contract in action, never required for learning.

## Ecosystem differences worth knowing

These are the honest asymmetries between the tracks; everything else is
mirrored.

| Concern | Python track | TypeScript track |
| --- | --- | --- |
| Interpreter/runtime pin | `.python-version` (3.12), enforced by uv | `.nvmrc` (20), honored by nvm/fnm and CI |
| Dependency lockfile | `uv.lock` | `pnpm-lock.yaml` |
| Package manager pin | uv resolves from `pyproject.toml` | `packageManager` field + corepack |
| Test runner | pytest | vitest |
| Linter | ruff | eslint (+ `tsc --noEmit` for types) |
| Running a source file | `uv run python file.py` | `pnpm exec tsx file.ts` (no build step) |

Where a lecture's implementation notes touch tooling (dependency locking,
version pinning, test runners), both ecosystems are shown side by side and
labeled. Where a template genuinely differs per ecosystem (the install lines
in `init.sh`), one shared file shows both, clearly marked.
