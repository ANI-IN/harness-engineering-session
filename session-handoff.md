# Session handoff

This module teaches session handoffs, so it keeps one. It follows
[library/templates/session-handoff.md](library/templates/session-handoff.md),
the template lecture 11 motivates, and `make resume` prints it.

Deliberately short. A handoff nobody reads is a handoff that failed.

## Verified now

- `make status` green: every gate (doctor, verify-dedup, conformance, lint,
  lint-links, lint-mermaid, lint-structure, lint-shared-helpers,
  check-fresh) exits 0.
- Counts sit exactly on their floors: 44 conformance units, 44 verify
  scripts, 13 lectures, 25 exercises, 5 projects, 96 README command fences.
- `make check-fresh`: 44 units, 484 checks, 0 failures, against an export
  of tracked content only.
- Both tracks verified from that export: 50 units passed in Python and 50
  in TypeScript, 0 failures.

## Changed most recently

- Lecture 05 merged into lecture 11; lectures renumbered to 01-13.
- Three demos that shipped wrong material fixed: substring matching in
  lecture 01, a discarded instruction file in lecture 02, and asserted
  rather than measured coverage in lecture 09.
- Two exercises replaced so lectures 12 and 13 test their own material, and
  starter defects spread across off-by-one, malformed line, empty input and
  wrong tie-break.
- Terminology unified to the module vocabulary, with one meaning each for
  layer, tier, seam and plug point.

## Broken or unverified

Nothing red. Two things to know before trusting a green run, both under
Open concerns: `make status` is not reliably green on a static tree, and
the README-command gate was timing-dependent until recently.

## Next best step

The module is complete and gated. The work that would most improve it:

1. Find the cause of the `kb-data` nondeterminism (first open concern). It
   is the only known way this repository fails on a tree nobody touched.
2. Unify the TypeScript workspace type in lecture 13's demo, currently a
   declared `Helper-divergence` rather than a fix.
3. Give lecture 06 a demo whose failure comes from content rather than
   budget arithmetic. It satisfies the behavioral-demo rule but
   demonstrates subtraction rather than a workspace going wrong.

## Open concerns

**`make status` is not reliably green on a static tree.** This is the one a
contributor most needs to know. A full run intermittently leaves an empty,
gitignored `projects/<project>/kb-data/` behind, and it can also fail
outright on a tree nobody has touched.

Measured across a fixed protocol, each run starting from a tree with no
`kb-data/` anywhere:

| | runs | left an empty `kb-data/` | failed the gate |
| --- | --- | --- | --- |
| before serializing the installer | 20 | 7 (35%) | 2 (10%) |
| after serializing the installer | 9 | 8 (89%) | 0 |

Read that carefully, because the obvious reading is wrong. Serializing the
installer fence did not leave the scratch unchanged: **the rate rose from
about 35% to about 89%, and the distribution narrowed**, from spread across
projects 01 to 04 down to project 03 in seven of the eight cases. Changing
the timing changed the symptom sharply, which is evidence that the cause is
timing-dependent and that project 03 is where to instrument first.

The gate failures are the more serious half. Two of twenty runs failed
`make status` on an unchanged, committed, green tree. That rate is
unmeasured after the change (0 of 9 is too few to mean anything), so **do
not read a single green run as proof**. Run it twice before concluding a
change is clean.

Ruled out, each clean in isolation, so do not repeat this bisect:
`make doctor`, `make verify-dedup`, `make conformance`, `make lint`,
`make lint-links`, `make lint-mermaid`, `tools/check_readme_commands.py`
alone, project 02's `verify.sh`, its pytest suite, its vitest suite, and
`tools/gen_readme_blocks.py`. Only a complete `make status` reproduces it.
The installer race, once the most promising lead, is ruled out by the
measurement above: it explained a CI failure and the false reds, not this.

`lint-structure` no longer reports the empty directory, so the symptom is
quiet. That was right for determinism and wrong for visibility, which is
why this entry exists.

**The newest lead, and the most concrete one.** A later run produced the
scratch under a different name: `kb-data 2`, in four projects at once. That
name is what a copy produces when its destination already exists, so at
least one fence copied a corpus into a `kb-data/` that a sibling had not
finished removing. That points squarely at the interaction between a
project's own `rm -rf $P/kb-data && cp -R ...` fences and the gate's
`finally` cleanup of the same path, rather than at the toolchain. Start
there: `run_readme_fences` in `tools/check_readme_commands.py`, and project
04's `Demo flow` fences. `.gitignore` now covers `kb-data*` so the collided
form cannot read as curriculum content while the cause is unknown.

**Every green the README-command gate produced before the installer was
serialized was partly a report about the machine's core count.** The gate
ran fences through a six-worker pool with `make setup` inside it, so
`pnpm install` could remove a binary a sibling fence was launching. It
failed CI once while sixty-one fences of the identical form passed in the
same run. Fixed by classification rather than timing, but historical greens
carry that caveat.

**Lecture 13 declares two `Helper-divergence` entries.** One is
legitimate. The other, its TypeScript workspace type, is an arbitrary
difference from the two lectures that share the helper; unifying is the
tidier end state and was declined late in the build because the unit was
green and the change is twenty-one call sites.

**Link exceptions expire.** `tools/lint/link_exceptions.json` fails any
entry older than thirty days. One remains, for a site that answers 403 to
automated fetchers. Re-verify and re-date it, or remove it.

## Standing conventions

[docs/conventions.md](docs/conventions.md) is authoritative and
machine-enforced. The rules most easily lost, and why they exist:

- **Lecture demos are behavioral.** A demo shows the claimed failure
  happening, with the outcome in the exit code. A metric may support a
  demo; it cannot be one.
- **Starters are genuine partials.** One realistic mistake, whose first
  divergence is a value mismatch naming the concept, never a formatting
  artifact and never null-versus-value.
- **Four acceptance runs per exercise**, starter and solution in both
  tracks, re-executed by `verify.sh --target=ci`.
- **Floors move in the commit that lands a unit**, set to the exact
  discovered counts, with the gates green against the raised floors.
- **No invented numbers.** Every figure is generated from a committed
  fixture, cited to a primary source, or labeled a heuristic.
- **No roadmap language**, and the module names itself correctly. Both are
  lint rules because both drifted back after being fixed once.
- **Declared escapes are the only escapes**: `Starter-shape: non-code`,
  `Starter-divergence justification:`, `Corpus-divergence:`,
  `Helper-divergence:`, and a SPEC section headed `Seeded defects`.

## Commands

- Start here: `make resume`, then `make setup`, `make doctor`.
- The commit gate: `make status`. Run it twice before concluding a change
  is clean, for the reason under Open concerns.
- Inner loop for one unit: `make quick U=<unit-dir>`. Never the gate.
- Before committing a lecture: `make lint-links-external` (needs network).
