# Exercise 01: handoff-roundtrip

## Objective

Fix the parser and the renderer so a session handoff round-trips between
markdown and JSON byte-identically, matching both shared expected files.

## Why this matters

[Lecture 05](../../README.md)'s continuity artifacts only work if the next
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

1. Fix `parse`: store each item without the "- " bullet prefix; the
   marker is markdown syntax, not content.
2. Fix `render`: emit the blank line between a section heading and its
   items, per the canonical format.
3. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: the stripped prefix corrects every item
value in the parse case, and the restored blank line makes the render case
byte-identical to the canonical markdown.

## Expected outcome

Before your change:

```text
[FAIL] parse (python) -- stdout mismatch vs expected/handoff.json: diverges at $.sections[0].items[0]: '- `./verify.sh import-notes`: exit 0' != '`./verify.sh import-notes`: exit 0'
```

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
<summary>Hint 1: each fix is one line</summary>

The parser's fix changes what is pushed into `items`; the renderer's fix
adds one `parts.append("")` / `parts.push("")` in the right place. The
solution's structure is already in the starter.

</details>

<details>
<summary>Hint 2: let the expected files arbitrate</summary>

If you are unsure what canonical form means, diff your output against
`expected/handoff.md`: the render case's expected file IS the format
definition, byte for byte.

</details>

## Solution walkthrough

Two one-line fixes, one law:

- **Markers are syntax.** Storing "- " inside the data means every
  consumer must strip it (or double it on re-render, which is exactly what
  the naive pair does on a second round-trip). Content and serialization
  stay separable or the format rots.
- **Canonical form is what makes byte-identity meaningful.** The blank
  line is not cosmetic: without a single canonical rendering, "round-trips
  exactly" degrades to "round-trips approximately", and approximate state
  files are how session 2 mistrusts session 1. The committed expected
  files pin the law so neither track can drift from it.

Cross-track note: both parsers are the same three-branch line scanner;
Python slices with `line[2:]`, TypeScript with `line.slice(2)`, and the
shared expected files hold both to identical output.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-05-why-long-running-tasks-lose-continuity/exercises/exercise-01-handoff-roundtrip -->
```text
starter/python: exit 1 (as intended: diverges at $.sections[0].items[0]: '- `./verify.sh import-notes`: exit 0' != '`./verify.sh import-notes`: exit 0')
starter/typescript: exit 1 (as intended: diverges at $.sections[0].items[0]: '- `./verify.sh import-notes`: exit 0' != '`./verify.sh import-notes`: exit 0')
solution/python: exit 0 (PASS: pass (2 checks))
solution/typescript: exit 0 (PASS: pass (2 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
