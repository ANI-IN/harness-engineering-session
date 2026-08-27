# AGENTS.md

You are working in **the Harness Engineering course repository**, a
dual-stack (Python + TypeScript) curriculum where every runnable unit
implements a shared `SPEC.md` against shared fixtures and expected outputs.
This repo is itself harnessed with the artifacts it teaches; this file is the
entry point. It is a router; depth lives in the linked docs.

## Startup workflow

1. `make resume`: prints `session-handoff.md` when a previous session left
   work in flight (the exact next unit, the first command, and the
   standing rules that live nowhere else). Read all of it before anything
   else; when it is absent, nothing is in flight.
2. `make setup`: install both toolchains; `make doctor` confirms the pins.
3. Read [docs/conventions.md](docs/conventions.md): the standard every
   folder follows. It is authoritative.
4. `make status`: confirm every gate is green before changing anything.

## Working rules

- **Both tracks or neither.** Any change to a runnable unit lands in
  `python/` and `typescript/` and passes `make conformance`. One track
  passing is not done.
- **Shared files are the contract.** Fix divergence in `SPEC.md` and the
  implementations, never by forking `expected/` per language.
- **Four runs per exercise**: starter fails for the intended reason and
  solution passes, in both tracks, every time an exercise changes.
- Terminology comes from [docs/glossary.md](docs/glossary.md): one term per
  concept.
- No invented numbers; claims are demonstrated, cited, or labeled heuristics.
- No network after setup; no API keys; deterministic fake agents where a
  model would sit.

## Verification commands

- Everything: `make verify && make conformance && make lint && make lint-links && make lint-mermaid && make lint-structure`
- One unit: `./<unit>/verify.sh --stack=python|typescript|both`

## Definition of done

- [ ] The relevant `verify.sh` and `make conformance` exit 0.
- [ ] All lint targets pass.
- [ ] New content follows the README section orders in conventions.md.
- [ ] Cross-links added both directions (lecture ↔ exercise ↔ project).
- [ ] The same commit that lands a unit bumps `tools/expected_counts.json`,
      and `make conformance` + `make verify` ran green with the raised
      floors before the commit.

## End of session

1. Run the full verification command; fix or record failures honestly.
2. Commit completed units only, one unit per commit, naming tracks verified.
3. Leave no scratch files or debug output in the tree.
