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

## Next best step: the full review

The module is complete, gated and published. The next session runs a
review across the whole tree. Everything it needs is below; it needs no
conversation history.

### The five areas

1. **Fresh-checkout walkthrough, both tracks.** Use the `check-fresh`
   export rather than a clone, since tracked content is the stricter
   test. Run every unit's `verify.sh` per track inside the export;
   exercises need `--target=ci`.
2. **Terminology sweep.** Every term against `docs/glossary.md`, which is
   authoritative and defines each term once. Look for a term meaning two
   things in two units, which is the worst failure mode, and for terms
   used repeatedly that the glossary never defines.
3. **Duplication check.** Each lecture defends one claim no other lecture
   defends, and each demo demonstrates a distinct behavior. Look for
   claims that overlap, demos that differ only in scenery, and exercises
   that plant the same defect twice.
4. **Weakest learning material.** A quality judgement, not a compliance
   check: every unit already passes the gates, so do not report gate
   compliance. Ask whether the demo teaches the claim or merely satisfies
   the rule that a demo must exist, whether a learner could apply the
   mechanism in their own repository the next day, and whether each
   starter's mistake is one a real engineer would make.
5. **Open concerns.** What is still unresolved, and what a contributor
   would trip over.

### How to run it

- **Read-only, findings only.** A review reports; it does not edit. Fixes
  come after, as a separate decision by the repository owner.
- **Priority order** when time is limited: correctness defects that ship
  wrong material first, then structural problems (duplication, a unit
  testing another unit's topic), then terminology and documentation. A
  wrong claim in committed material outranks an inconsistent word.
- **Verify before passing anything through.** If a subagent produces a
  finding, re-execute or re-read the evidence yourself before repeating
  it. During the build a subagent reported that lecture 09 over-counted
  seam coverage on a fixture; running it showed the number was right for
  that fixture and the real defect was narrower. Passing the unverified
  version through would have been wrong in public.

### Already known, do not re-report as new

- **Lecture 06's demo is the weakest of the behavioral set.** Its failure
  comes from budget arithmetic (a step counter running out) rather than
  from content going wrong in a workspace. It satisfies the
  behavioral-demo rule. The owner has seen this and chose to leave it.
- **The synced-folder nondeterminism is closed and is not a repository
  defect.** See Open concerns. `make doctor` warns about it by name.
- **Project 06 (the capstone) and the skills pillar are deliberately
  unbuilt.** The module ships as 13 lectures, 25 exercises, 5 projects
  and the library pack. Nothing in the tree describes more than that, and
  that was verified. Do not report them as gaps.
- **Lecture 13 carries two declared `Helper-divergence` entries.** One is
  legitimate; the other, its TypeScript workspace type, is arbitrary and
  was declined late in the build. Recorded, not forgotten.

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

**Nothing in this repository needs fixing for it**, and `make doctor` now
detects it: a working copy inside iCloud, Dropbox, OneDrive or Google
Drive, including the macOS Desktop and Documents redirect, produces a loud
warning naming the client and the fix. It warns rather than fails, because
it is the user's machine. Use an unsynced path such as `~/src`. The two defensive changes made while the cause was
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
