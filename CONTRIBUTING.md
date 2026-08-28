# Contributing

Thanks for improving the module. This repository holds itself to the standard
it teaches: every change is verified by executable checks, both language
tracks stay at parity, and the conventions are machine-enforced.

## Setup

```sh
make setup     # installs both toolchains (uv + pnpm)
make doctor    # verifies your versions against the pins
```

Pins: Python 3.12 (`.python-version`, installed by uv), Node 20 LTS
(`.nvmrc`), pnpm via the `packageManager` field (activate with
`corepack enable pnpm`).

## Before you open a pull request

Run the full gate locally; CI runs these plus `make setup`, `make doctor`, `make lint-shared-helpers`,
`make lint-authorship`, and `make check-fresh`:

```sh
make verify && make conformance && make lint && \
make lint-links && make lint-mermaid && make lint-structure
```

## The rules that are not negotiable

1. **Dual-track parity.** Any change to a runnable unit lands in both
   `python/` and `typescript/`, produces identical normalized output, and
   passes `make conformance`. One track passing is not done.
2. **Four runs per exercise.** A changed exercise is re-verified four ways:
   starter fails (for the intended reason) and solution passes, in both
   tracks.
3. **Shared files are the contract.** `SPEC.md`, `fixtures/`, and `expected/`
   are written once. If the tracks disagree after normalization, fix the spec,
   and never fork the expected outputs per language.
4. **No invented numbers.** Claims about agent behavior are demonstrated by a
   demo, cited to a primary source, or framed as a design heuristic.
5. **Conventions are law.** [docs/conventions.md](docs/conventions.md) defines
   naming, README section orders, diagram rules, and the verification
   contract; `make lint-structure` enforces them.
6. **Offline.** No unit may need network after `make setup`, and no API keys
   ever. Where a real model would sit, use the deterministic fake agent and
   document the seam.

## Making a change

- **Fixing content**: keep the README section order; run `make lint-links`
  (and `make lint-links-external` if you touched external URLs).
- **Changing a demo or exercise**: update `SPEC.md` first, then both
  implementations, then `expected/`; run the unit's `verify.sh --stack=both`
  and `make conformance`.
- **Adding an exercise or unit**: follow the directory shape in
  conventions.md exactly; `lint-structure` rejects incomplete units.
- **Changing templates** (`library/templates/`): these are single-sourced for
  the entire module; `make verify` validates them (JSON against schema,
  init.sh via shellcheck).

## Commit style

- One completed, verified unit of work per commit.
- Message: imperative summary naming the unit and, for curriculum code, the
  tracks verified, e.g. `lecture-03: add repo-reader demo (py+ts verified)`.
- No co-author trailers or tool attributions. `make lint-authorship`
  enforces this over `main..HEAD` and runs inside `make status` and CI. It
  reads each commit's full body: a trailer is not visible in the author or
  committer fields, which is how three of them once shipped.

## Reporting problems

Open a [GitHub issue](https://github.com/ANI-IN/harness-engineering-session/issues) with the
command you ran, full output, and your `make doctor` report. A `verify.sh`
that fails on a fresh clone is always a bug here, never user error.
