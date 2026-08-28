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

Nothing red. One environment caveat under Open concerns: do not run the
gates inside a synced folder. That was the cause of a nondeterminism
chased for most of the build, and it is not a defect in this repository.

## Next best step

The module is complete and gated. The work that would most improve it:

1. Unify the TypeScript workspace type in lecture 13's demo, currently a
   declared `Helper-divergence` rather than a fix.
2. Give lecture 06 a demo whose failure comes from content rather than
   budget arithmetic. It satisfies the behavioral-demo rule but
   demonstrates subtraction rather than a workspace going wrong.

## Open concerns

**Closed: the `make status` nondeterminism was iCloud, not this
repository.** For most of the build a full gate run intermittently left an
empty `projects/<project>/kb-data/` behind, and twice failed outright on an
unchanged, committed, green tree. No single gate reproduced it, and
serializing the installer fence moved the rate from about 35% to about 89%
without curing it, which was the clue: changing timing changed the symptom,
so the cause was not any gate's logic.

The name that settled it was `kb-data 2`. Three checks, none of which point
at this repository:

1. `cp -R src dst` with an existing `dst` produces `dst/src`, never a
   numbered sibling. Verified directly. So no fence produced that name.
2. A numbered duplicate of git's own index, `.git/index 2`, was sitting in
   the repository. Nothing here writes `.git/index`, and git never creates
   numbered siblings.
3. The working copy lives under `~/Desktop`, and
   `~/Library/Mobile Documents/com~apple~CloudDocs/Desktop` exists with
   CloudDocs actively syncing.

Numbered duplicates are iCloud's conflict-copy convention. iCloud was
racing the working tree: recreating directory shells the gates had just
removed, and mutating files (including `.git/index`) mid-run, which is why
`make status` could fail on a tree nobody had touched.

The competing hypothesis was tested head-on rather than by elimination. A
project's own `rm -rf $P/kb-data && cp -R ... $P/kb-data` fence was run
against a concurrent `rm -rf` of the same path, forty rounds, in a
directory outside any synced folder. It can leave a plain `kb-data`
behind, which is ordinary ordering, and it produced **no numbered
duplicate at all**. Fences touching the same `kb-data` are also already
serialized, because fences within one README run in order in one worker
and different READMEs own different paths. So the fence race is not the
cause of what was observed.

**Nothing in this repository needs fixing for it.** Do not run the gates
inside iCloud Drive, Dropbox, OneDrive or any synced folder; use a local
path such as `~/src`. The two defensive changes made while the cause was
unknown are kept because they are right on their own merits: the orphan
check ignores gitignored scratch, since scratch is not curriculum, and
`.gitignore` covers `kb-data*` so a conflict copy cannot read as content.

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
