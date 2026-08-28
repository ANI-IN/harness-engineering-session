# AGENTS.md

You are working in **the Harness Engineering module repository**, a
dual-stack (Python + TypeScript) curriculum where every runnable unit
implements a shared `SPEC.md` against shared fixtures and expected outputs.
This repo is itself harnessed with the artifacts it teaches; this file is the
entry point. It is a router; depth lives in the linked docs.

## Startup workflow

1. `make resume`: prints HEAD, the unpushed count and the tree state, plus
   `session-handoff.md` when one is present. That handoff is deliberately
   **not** committed here: it is working state, not curriculum, so a clone
   does not carry one and `make resume` will say nothing is in flight. The
   artifact itself is still taught, by lecture 11 and
   [library/templates/session-handoff.md](library/templates/session-handoff.md),
   and every project ships one in its `harness/`.
2. `make setup`: install both toolchains; `make doctor` confirms the pins.
3. Read [docs/conventions.md](docs/conventions.md): the standard every
   folder follows. It is authoritative.
4. `make status`: confirm every gate is green before changing anything.

## Audience

Experienced software engineers who are already fluent in agentic AI. Assume
working familiarity with LangChain, LangGraph, MCP, A2A, Google ADK,
multi-agent systems, and LangSmith. They have built agents; what they have
not built is the execution system that makes an agent's work reliable.

Harness engineering is the new material. Agents are not. So:

- Do not introduce agent concepts, orchestration frameworks, or tool
  calling. Reference them and move on.
- Do not define terms this audience uses daily. Define only the terms this
  module gives specific meanings to, and put those in
  [docs/glossary.md](docs/glossary.md#core-model).
- Cut any passage whose purpose is to bring a reader up to speed on agents
  rather than on harnesses.
- This audience detects hand-waving instantly, which is what makes the
  no-invented-numbers rule load-bearing rather than stylistic. Every figure
  is generated from a committed fixture, cited to a primary source, or
  labeled a heuristic.

## Working rules

- **Both tracks or neither.** Any change to a runnable unit lands in
  `python/` and `typescript/` and passes `make conformance`. One track
  passing is not done.
- **Shared files are the contract.** Fix divergence in `SPEC.md` and the
  implementations, never by forking `expected/` per language.
- **Four runs per exercise**: starter fails for the intended reason and
  solution passes, in both tracks, every time an exercise changes.
- Terminology comes from [docs/glossary.md](docs/glossary.md#core-model): one term per
  concept.
- No invented numbers; claims are demonstrated, cited, or labeled heuristics.
- No network after setup; no API keys; deterministic fake agents where a
  model would sit.

## Verification commands

- Everything: `make status` (every gate, with counts against the floors).
- Everything, longhand: `make verify && make conformance && make lint && make lint-links && make lint-mermaid && make lint-structure && make lint-shared-helpers && make lint-authorship && make check-fresh`
- One unit: `./<unit>/verify.sh --stack=python|typescript|both`
- Before committing a lecture, additionally: `make lint-links-external`.

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
