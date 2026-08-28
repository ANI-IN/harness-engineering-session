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
  scripts, 13 lectures, 25 exercises, 5 projects, 105 README command
  fences. Note that `make status` prints only the first five; the fence
  floor is enforced by `check_readme_commands.py` inside the verify gate
  and appears in the root README's generated counts block.
- `make check-fresh`: 44 units, 484 checks, 0 failures, in both tracks,
  against an export of tracked content only. That is the whole of what
  `check-fresh` runs: the conformance suite inside the export, three ways
  per case. It does not invoke each unit's `verify.sh`.

## Changed most recently

- Lecture 05 merged into lecture 11; lectures renumbered to 01-13.
- Three demos that shipped wrong material fixed: substring matching in
  lecture 01, a discarded instruction file in lecture 02, and asserted
  rather than measured coverage in lecture 09.
- Two exercises replaced so lectures 12 and 13 test their own material, and
  starter defects spread across off-by-one, malformed line, empty input and
  wrong tie-break.
- Terminology partly unified to the module vocabulary. This previously
  claimed one meaning each for layer, tier, seam and plug point; the
  review found all four still colliding, so the claim is withdrawn and
  the work is backlog item 16.

## Broken or unverified

Nothing red: every gate exits 0 and every count sits on its floor. Not the
same as nothing known, though. The review found and verified 24 items, 1 since fixed and 23 still open, that
were deliberately left, listed under the backlog below with severity and
cost. Read that section before concluding the tree is finished.

One environment caveat under Open concerns: do not run the gates inside a
synced folder. That was the cause of a nondeterminism chased for most of
the build, and it is not a defect in this repository.

## Changed in this session: the full review, and the fixes taken from it

The tree-wide review ran read-only over five disjoint areas (lectures
01-06, lectures 07-13, projects 01-05, tooling, docs and library) and
produced a ranked list. Everything the owner chose to fix before the
session is applied and green. What was deliberately deferred is the
backlog below, kept here so the list survives without the conversation
that produced it.

### Fixed

- **Three exercise READMEs and SPECs documented work that was already
  done, or a rule that was not in the table.** Exercise 06-02's README
  described the two evidence checks the starter already implements while
  the real task (refuse a feature declaring no verification command)
  appeared only in a code comment, and its SPEC's rule table omitted that
  rule entirely. Exercise 02-01's README named tools, environment and
  state as the naive audits when the starter's real defects are tools and
  feedback, said six fixture repositories where there are seven, and its
  SPEC's feedback criterion still described the starter's behavior. Both
  starters' docstrings carried the same stale claims.
- **Lecture 13 sent learners to a replaced exercise**, describing a
  journal-replay exercise with a walk-forward seeded mistake. Exercise 01
  is a static graph validator whose mistake is a first-writer tie-break.
- **Six documented commands did not work as written.** Five project
  READMEs showed bare `./verify.sh` under `Testing and validation`, a
  section `check_readme_commands.py` does not scan, and that path does not
  exist from the repository root the READMEs mandate. Project 02's Demo
  flow step 3 showed `--workspace harness`, which exits 2 from the root.
- **Two false claims about our own enforcement.** The README said a lint
  rule enforces no-invented-numbers; `check_prose.py` enforces dashes, the
  module-naming rule and roadmap phrases, and nothing reads a prose figure.
  The README also named three sources as the only places external claims
  come from, while lectures 04 and 08 carry `Source:` lines to two arxiv
  papers among a dozen other cited URLs.
- **`conventions.md` said nine lecture demos carry the same helper; the
  real maximum is three.** The registry had drifted to five names, two of
  which had one copy each and were therefore compared against nothing, so
  the gate's printed count overstated what it held.
  `check_shared_helpers.py` now reports comparisons rather than registry
  size and fails on a registered name with fewer than two copies.
- **Two figures in this handoff were wrong**: 96 README command fences
  (the floor was already 102) and "50 units passed in Python and 50 in
  TypeScript", a number no tool here emits. `check-fresh` runs the
  conformance suite inside the export and nothing else.
- **Three library templates named the wrong motivating lecture.**
  `init.sh` cited lecture 06 for lecture 05's title, and
  `clean-state-checklist.md` cited lecture 05 twice for lectures 08's and
  11's titles. These are files learners copy out.
- **The session minute table over-allocated the four hours by 85
  minutes**, stamping each shared block's full duration on both member
  lectures, and marked lectures 01 and 03 as both live and read.
  `docs/session-plan.md` was already correct.
- **The root README's walkthrough showed only Python**, in a dual-track
  module, in its only end-to-end section. Both tracks now run there; the
  fence floor moved 102 to 105 in the same change.
- **`make setup` silently rewrote lockfiles.**
  `pnpm install --frozen-lockfile || pnpm install` converted the failure
  the flag exists to raise into a rewrite, and CI runs that target.
- Project 01's README claimed 17 pytest and 17 vitest; both are 18. The
  root README pointed at a counts block "at the top of this file" that is
  36% in. Nine lecture demo `verify.sh` scripts printed a lecture number
  one higher than their own, lecture 13 printing `verify(lecture-14 ...)`,
  which does not exist, and lecture 04 named a unit called
  `instruction-stats` where the unit is `instruction-walk`. Eight files
  misnamed this module as a sequence of modules, the thing
  `lint-prose` exists to catch and cannot see outside markdown, including
  the JSON Schema and the five project `harness/init.sh` files that
  learners copy.

### Backlog: found, verified, deliberately not fixed

Severity and cost are from the review and were confirmed by re-executing
each item's evidence. Nothing here is a guess.

**HIGH. Gates that report green without checking.** This is the cluster
worth taking first, and the first item is the one that would embarrass
the module fastest in front of an audience that greps.

- **1.** **FIXED (commit `598cf6b`).** `make status` printed "coverage
   equality is proven by `tools/test_dedup_coverage.py`" when nothing
   established it. The note and `docs/conventions.md` now say what is
   actually checked (three structural preconditions) and state plainly that
   equality is established by inspection, not proven. Left in this list as
   a record; nothing to do.
- **2.** **The projects' only starter-must-fail assertion cannot detect its own
   removal or its disabling.** `tools/test_dedup_coverage.py:67-77`, three
   independent breaks: a project that loses its gate is `continue`d past;
   the position assertion is satisfied by both the correct and the
   inside-the-guard layout; and the brace-counting heuristic reduces to
   `N >= M`, which holds either way. The module docstring promises this
   test fails the build when a project loses its starter gate. Cost: one
   file.
- **3.** **A tautological invariant labelled "asserted rather than assumed".**
   `tools/check_readme_commands.py:207-214`. `escaped` filters the
   parallel list on the predicate whose `else` branch populated it, so it
   is provably always empty. Cost: one line.
- **4.** **"Conformance byte-equality carries the proof to the TypeScript
   track" is invoked twice to justify absent TypeScript negative
   coverage, and it is invalid.** Project 04's TS suite has one guard test
   (the healthy path) against Python's three injected violations, and the
   only guard conformance case is on a healthy fixture. Project 03's
   process boundary is an explicit SPEC contract whose asserted field is a
   hardcoded string literal, with the only real gate Python-only
   (`test_kb_v3.py:110`). Byte-equality of a passing report proves nothing
   about detection, and `AGENTS.md` says both tracks or neither. Cost: one
   unit each.
- **5.** **Lectures 01 and 02 put no verdict in the exit code.** Lecture 01's
   demo emits a ratio and exits 0; lecture 02's five ablations produce
   `blocked`, `error`, `failed-verification` and `claimed-unverified` and
   all exit 0. Neither README carries a `fence-exit` marker. Lectures
   03-13 all put the failure in exit 1. `conventions.md:271-274` says a
   metric may support a demo but cannot be one; `:277-278` exempts only
   "lectures 05-13" and is silent on 01-03. Cost: one line each to add the
   verdict, or a documented carve-out.
- **6.** **`check_build_state.py:30-44` never inspects the outcomes it
   records.** Key presence only, so a build state asserting every starter
   passed and every solution failed returns OK. The file is also
   gitignored, making the gate inert in CI and in every clone, which
   `conventions.md:243-245` does not say. Cost: one file.
- **7.** **Exercise 07-01's central rule is asserted by no case.** All four
   `to: passing` requests target `cart`, so an implementation hardcoding
   `"./verify.sh cart"` instead of reading the feature's own
   `verification` passes every case, in the exercise whose stated point is
   tying evidence to that field. Rows 4 and 9 of its nine-row rule table
   have no case at all. Cost: one unit.
- **8.** **A latent parity violation.** Exercise 11-02 uses `text.index` in
   Python and `text.indexOf` in TypeScript. On a `claude-progress.md` with
   no `## Session` heading line, Python exits 1 with an unhandled `ValueError`
   and TypeScript exits 0 claiming success. No committed fixture reaches
   it, so conformance cannot see it. `conventions.md:133-135` calls this a
   spec bug in the unit. Cost: one unit.

**MEDIUM. Unsupported claims and unreachable paths.**

- **9.** Lecture 02's SPEC declares a `run_check` permission the code never
   reads (removing it from `tools.json` changes nothing) and hardcodes
   `stamp-header` where the SPEC says the value is derived from the
   project summary. One file.
- **10.** Lecture 04 claims its two fixture trees "carry the same rules" in what
    it frames as a controlled-variable comparison; the monolith has 17
    tagged rules and the router 15, with two `[overview]` lines only in
    the monolith. The same README says the router's constraint "sits at
    the top" where the unit's own pinned output records `zone: middle`.
    One line plus one file.
- **11.** Lecture 05's README says the missing progress log costs three steps of
    re-derivation; the SPEC prices it at 2 and the generated block reports
    `setup_overhead: 5` with exactly two re-derivation events. One line.
- **12.** Lecture 01's SPEC rule table terminates at a blank line, so the
    `state` and `feedback` rows render as raw pipe characters. Those are
    two of the three rules exercise 01-01 asks the learner to implement,
    and that exercise delegates its definitions to this file. One line.
- **13.** Lecture 09's SPEC documents a component field named `layer`; the real
    field is `tier`, so an `app.json` written from that schema block
    raises `KeyError`. The same SPEC calls tiers "layers", which the
    glossary defines as distinct. One file.
- **14.** **Six documented failure paths no committed fixture can reach**:
    lecture 05's doctor (no dependency manifest, `init.sh` missing,
    `init.sh` not executable, no Verification line), lecture 03's
    documented `CLAUDE.md` fallback, exercise 04-01's `entry-length`
    violation branch, exercise 08-01's `green` field (all 15 claim rows
    are `pass`, so it cannot differ from `len(checks)`), exercise 09-02's
    `blind` verdict and exit 1, and lecture 13's `unreachable` arm. One
    file each.
- **15.** Lecture 13's prose says `graph-no-rollback` is "the same four nodes
    with one edge changed" and "one edge removed from one node"; the
    fixture removes the `fail` edge and the whole `undo` node, 5 nodes to
    4, and the README's own generated block reports 5/4/5. That extra
    removal is why item 14's `unreachable` arm has no case. One file.
- **16.** **Terminology: both pairs this handoff previously recorded as unified
    still collide.** `seam` and `plug point` name the same concept in six
    places each, colliding inside lecture 08 and inside lecture 10 (SPEC
    says one, the code comment says the other), with lecture 12 against
    lectures 11 and 13, and `CONTRIBUTING.md:45`. `tier` and `layer`
    collide per item 13. Cross-cutting, roughly seven files.
- **17.** `visibility_gap` has two definitions inside lecture 03's own tree:
    unanswered questions over five in the demo SPEC, decisions outside the
    repository over total in exercise 02. The lecture's Concepts section
    defines only the second, and its 10% heuristic applies only to the
    second, while the demo prints the first. One line plus one file.
- **18.** `projects/README.md:40` pairs project 03 with lectures "05, 11" while
    project 03's own README, lecture 11's README ("No project is dedicated
    to this lecture") and the curriculum map's graph all say otherwise;
    separately `docs/curriculum-map.md:13` lists lectures 10, 12 and 13 as
    unpaired and omits 11. One line each.
- **19.** Project 05's `harness/AGENTS.md:47` says `evaluator-rubric.md` "is
    executed by `kb score`". Nothing reads that file; `RUBRIC` is a
    hardcoded tuple at `main.py:979`. One line, or one unit to make it
    true.
- **20.** Three SPEC delta rows claim harness docs were "updated for v4/v5"
    while being byte-identical to the previous project's copy but for the
    H1: `INDEXING.md` omits `corrupt` (v4's headline addition) in projects
    04 and 05, project 05's `ARCHITECTURE.md` omits `kb delete`, and its
    `PRODUCT.md` carries a v4 preamble above a 17-feature v5 list. One
    file each.
- **21.** Four conformance cases were dropped across the project accretion with
    no declaration (`ask-no-match`, `import-duplicate-skipped`,
    `status-unindexed`, `ask-before-index`), and three behaviors lose all
    coverage by project 05 while the rising case counts mask it. One unit,
    or a declaration in the delta tables.
- **22.** Two `conventions.md` rules the tree does not follow: "every directory
    under lectures/, projects/, library/, tools/ has a README.md" (601 of
    652 lack one; the gate checks the four roots and their immediate
    children only), and `uv run pytest <unit>/python/tests`, which
    resolves for zero units and contradicts `:72-73` in the same file. One
    line each.
- **23.** `glossary.md:168` says lectures 08 and 09 both use check layers
    "static, then tests, then system"; lecture 09's declared layers are
    `unit` and `e2e`. One line.
- **24.** Smaller machinery gaps: `--root` is a dead flag on the conformance
    runner whose only effect is disabling the unit floor; `lint-sh`,
    `lint-mermaid` and `lint-md` pass vacuously on an empty discovery with
    no floors; nothing enforces the one-diagram-per-README or
    no-`classDef` rules that `conventions.md:390-396` states;
    `report_status.py` omits the fence row it enforces, which is how a
    stale fence count survived here unchallenged. One line each.

**LOW, not itemized further.** Exercise 11-03 calls itself "Exercise 01"
in three places including runtime output (the lecture 05 merge seam);
exercise 01-01's starter is fill-in-three-blanks rather than one realistic
mistake, and its recorded divergence names a ratio rather than a concept;
lecture 03's README says the unanswered entries name the artifact that
should exist, where they are `null`; a Python-only dead `render()` in
exercise 09-02; lecture 11's "identical through step N" counts matching
pairs rather than a common prefix (correct on the committed data, latent
in method); a duplicated uninterpolated `BUILD_DATE`;
`test_check_readme_commands.py:66`'s floor of 26 against a real 105;
`test_the_warning_never_fails_the_doctor` never calls the doctor;
`test_dedup_skip_reaches_scripts_through_run_verify` never calls
`run_verify`; `doctor.run_version` reports `[ok]` for a present-but-broken
`uv` or `shellcheck`; the `stdin` case feature is documented, implemented
and used by no case; `run_acceptance.py`'s "4/4" is true by construction;
the `AGENTS.md` template's adoption instruction is followed by none of its
five consumers and three of eight templates are instantiated by one
project; `choosing-your-track.md` introduces "all harness templates" and
lists six of eight; `curriculum-map.md:42` omits `evaluator-rubric.md`;
`AGENTS.md:59`'s longhand omits `make doctor`.

### How the review was run, if it is repeated

- **Read-only, findings only, then a separate fix decision.** Five agents
  over disjoint areas, three at a time, each reporting file, line,
  severity and evidence, with anything lacking a reason to believe it
  wrong dropped rather than reported.
- **Re-execute every finding before repeating it.** Two agents' counts
  disagreed on a helper's copy count and one of my own greps was wrong
  (`read_key` matched `read_key_from_file`); the numbers above are the
  ones that survived being checked. An earlier build session saw a
  subagent report that lecture 09 over-counted seam coverage; running it
  showed the number was right and the real defect was narrower.
- **The territory cut beats the aspect cut** for parallel work: five
  directory areas are disjoint, so agents never raced, and the
  aspect-shaped questions (terminology, duplication, weakest material)
  fold in as standing questions each agent answers for its own area.

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

- **1.** `cp -R src dst` with an existing `dst` produces `dst/src`, never a
   numbered sibling. Verified directly. So no fence produced that name.
- **2.** A numbered duplicate of git's own index, `.git/index 2`, was sitting in
   the repository. Nothing here writes `.git/index`, and git never creates
   numbered siblings.
- **3.** The working copy lives under `~/Desktop`, and
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
