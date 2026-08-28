# Exercise 01: handoff-roundtrip

## Objective

Fix the parser and the renderer so a session handoff round-trips between
markdown and JSON byte-identically, matching both shared expected files.

## Why this matters

[Lecture 11](../../README.md)'s continuity artifacts only work if the next
reader (usually a program: the simulator, a status tool, an agent's
startup step) can rely on their structure. A handoff that parses is state;
a handoff that only humans can read is prose. The round-trip law is the
cheapest way to keep a format honest: whatever you parse, you must be able
to write back without loss.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Concepts](../../README.md#concepts) and the library's
  [session-handoff template](../../../../library/templates/session-handoff.md).
- [Lecture 03's fresh-session-answers](../../../lecture-03-why-the-repository-must-become-the-system-of-record/exercises/exercise-01-fresh-session-answers/)
  for the tagged-structure extraction mindset.

## Provided

- [`SPEC.md`](./SPEC.md): the canonical format, the parsed shape, and the
  round-trip law (shared).
- [`fixtures/handoff.md`](./fixtures/handoff.md) and
  [`fixtures/handoff.json`](./fixtures/handoff.json): one handoff in both
  representations (shared).
- [`expected/handoff.json`](./expected/handoff.json) and
  [`expected/handoff.md`](./expected/handoff.md): the grading authority;
  the expected markdown is byte-equal to the markdown fixture, which is
  the round-trip law as a committed check (shared; never edit them).
- `starter/{python,typescript}/main.py|ts`: both directions run, each with
  one naive mistake.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. Fix `parse`: keep every section, in document order; delete the
   "core sections" whitelist, which silently drops anything it does not
   recognize.
2. Fix `render`: preserve the document's own section order; delete the
   alphabetical sort.
3. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the parser stops dropping the
`Broken or unverified` section and the renderer stops reordering, so both
directions preserve the whole document and the round trip closes.

## Expected outcome

Before your change:

```text
[FAIL] parse (python) -- stdout mismatch vs expected/handoff.json: diverges at $.sections[2].heading: 'Next best step' != 'Broken or unverified'
```

A whole section of the handoff, the one naming what is known to be
broken, vanished between markdown and JSON.

After your change both cases pass, `render(parse(x)) == x` holds byte for
byte, and:

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
<summary>Hint 1: both fixes are deletions</summary>

The parser's fix removes the whitelist branch so every section heading
opens a section; the renderer's fix removes the sort so sections come out
the way they went in. The correct code is smaller than the naive code.

</details>

<details>
<summary>Hint 2: let the expected files arbitrate</summary>

If you are unsure what canonical form means, diff your output against
`expected/handoff.md`: the render case's expected file IS the format
definition, byte for byte.

</details>

## Solution walkthrough

Two deletions, one law:

- **A round trip must carry everything, known or not.** The whitelist
  encodes an opinion about which sections matter, and the section it
  drops (`Broken or unverified`) is exactly the one whose loss makes the
  next session re-discover a failure the last session already isolated.
  Parsers preserve; policies about relevance belong to readers, not to the
  serialization layer.
- **Order is content.** A handoff is read top to bottom under time
  pressure, so its section order is a priority ranking; sorting it
  alphabetically is a quiet form of data loss. Without a single canonical
  rendering, "round-trips exactly" degrades to "round-trips
  approximately", and approximate state files are how session 2 mistrusts
  session 1. The committed expected files pin the law so neither track can
  drift from it.

Cross-track note: both parsers are the same three-branch line scanner;
Python slices with `line[2:]`, TypeScript with `line.slice(2)`, and the
shared expected files hold both to identical output.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-11-why-every-session-must-leave-a-clean-state/exercises/exercise-03-handoff-roundtrip -->
```text
starter/python: exit 1 (as intended: diverges at $.sections[2].heading: 'Next best step' != 'Broken or unverified')
starter/typescript: exit 1 (as intended: diverges at $.sections[2].heading: 'Next best step' != 'Broken or unverified')
solution/python: exit 0 (PASS: pass (2 checks))
solution/typescript: exit 0 (PASS: pass (2 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
