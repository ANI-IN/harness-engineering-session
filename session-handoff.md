# Session handoff

Written 2026-08-28 at the end of the build session that landed lectures
07-09, for a fresh session with no memory of the conversation. Read all of
it, then start the [AGENTS.md](AGENTS.md) ritual. The template this
follows is [library/templates/session-handoff.md](library/templates/session-handoff.md);
the extra sections exist because the standing rules below are recorded
nowhere else.

## Verified now

- `make status` at commit `18f680e`: every gate exit 0 (doctor,
  verify-dedup, conformance, lint, lint-links, lint-mermaid,
  lint-structure); counts 33 conformance units, 33 verify scripts,
  9 lectures, 18 exercises, 5 projects, all exactly at the floors in
  [tools/expected_counts.json](tools/expected_counts.json); 58 README
  command fences (floor 58).
- Commits since the last push, all authored `Animesh Kumar
  <animesh.kcm@gmail.com>` and unpushed (15 at `18f680e`; the handoff
  commit makes 16): `ad44038` README-command gate, `3d16066` track-scoped
  setup/doctor, `a45a73b` lecture 04 behavioral demo, `d46dd9e` fixture-copy
  lint, `15ae708` parallel generated blocks, `9f6762f` workspace rename,
  `0c4cd3a` pre-1.0 contract declaration, `a811464` project 04, `0b94fe1`
  kb-data ignore fix, `da73a5d` roadmap-language gate, `c9e1e82` lecture 06
  replay demo, `929c10e` project 05, `16955a5` lecture 07, `4a32e02`
  lecture 08, `18f680e` lecture 09. **Push only when the user says so**;
  the last push authorization covered commits through `0d14d91`.
- Nothing is half-built. Batch two of the lecture fan-out (lectures 10,
  11, 12) was stopped at handoff time before any of its agents had written
  a file; `lectures/` contains 01-09 only.

## Changed this session (the last one before this handoff)

- Roadmap-language gate in `tools/lint/check_prose.py` (`da73a5d`).
- Lecture 06 gained the `replay` demo (`c9e1e82`); project 05 built
  (`929c10e`); lectures 07, 08, 09 built by subagents and integrated
  serially (`16955a5`, `4a32e02`, `18f680e`).
- Curriculum map, `lectures/README.md`, root `README.md`, and the project
  04/05 "Related lectures" sections now cover lectures 01-09 and projects
  01-05 in both directions.
- This handoff, the `make resume` target, and step 1 of the AGENTS.md
  startup workflow.

## Broken or unverified

- Nothing red. One integration catch worth knowing: the lecture 07 agent
  had not run ruff, and the whole-tree `make status` caught two E501
  line-length errors before the commit. Later briefs name ruff, eslint,
  and typecheck explicitly (the brief below already does).
- Known trap: empty `projects/<project>/kb-data/` directories fail
  `lint-structure` as orphan directories. They appeared once at handoff
  time (three empty dirs under project 04, most likely left by a stopped
  batch-two agent that had been exploring project 04's log surface) and
  did not recur on a quiet tree. If `make status` reports them, confirm
  they hold no files, remove them, re-run. `kb-data/` under projects is
  gitignored learner scratch; committed corpora live in `fixtures/`.
- Side effects of stopped subagents are otherwise unknown: the three
  batch-two agents were killed while reading, but check `git status` and
  `ls lectures/` before trusting this handoff's "nothing half-built".

## Next best step

Build lectures 10, 11, 12 by subagent fan-out (three concurrently, the
cap), then integrate each serially, then lectures 13 and 14 the same way
(two agents). The first command of the session, after the AGENTS.md
ritual, is `make status` (must print `status: OK`). Then launch three
subagents with the brief in "Subagent brief" below plus the per-lecture
prompt from "Per-lecture prompts". When a unit returns:

1. Re-execute its proofs yourself (do not trust the report):
   `uv run python tools/conformance/runner.py --unit lectures/<dir>/code`,
   `bash lectures/<dir>/code/verify.sh`, and for each exercise
   `bash lectures/<dir>/exercises/<ex>/verify.sh --stack=both --target=ci`.
   Capture exit codes with `> file; echo $?`, never through a pipe.
2. Record the four acceptance runs per exercise in `build_state.json`
   (gitignored, present on this machine; schema in "Local files" below).
   `make status` fails locally until every exercise in the tree has them.
3. Shared-file edits, yours only: a row in `lectures/README.md` and in the
   root `README.md` table; a back-link in the related project's
   "Related lectures" section; the lecture node and edges in
   `docs/curriculum-map.md` (its scope sentence must describe exactly
   what is in the map); floors in `tools/expected_counts.json` (+1
   lecture, +2 exercises, +3 conformance units, +3 verify scripts, and the
   fence count from
   `uv run python -c "import sys; sys.path.insert(0,'tools'); import check_readme_commands as c; print(len(c.discover_fences()))"`).
4. `make status` against the whole tree, exit 0, output captured.
5. Commit that unit only (its directory plus the shared-file edits), as
   `Animesh Kumar <animesh.kcm@gmail.com>`; check `git config user.name`
   and `user.email` first; a clean message describing the demo and the
   exercises; no AI attribution, no Co-Authored-By trailers, anywhere.

Integrate one unit at a time even when three return together. The tree
must be stable (no agent writing) while `make status` runs, so launch the
next batch only after the previous batch is fully committed.

## Standing rules beyond conventions.md and AGENTS.md

The user added these during the build. They are binding.

- **Behavioral demos over metrics.** A lecture demo must show the claimed
  failure happening (something attempts the task and observably fails,
  with exit code and report), then the mechanism preventing it. A metric
  may support a demo but cannot be one. Recorded in
  [docs/conventions.md](docs/conventions.md#lecture-demos-are-behavioral);
  lectures 04, 06, 07, 08, 09 are the exemplars.
- **Genuine-partial starters.** An exercise starter is a naive-but-real
  draft with one realistic mistake; its first divergence is a value
  mismatch that names the concept, never a formatting artifact or
  null-versus-value. Length or shape differences need the
  `Starter-divergence justification:` line in SPEC.md
  ([exercise anatomy](docs/conventions.md#exercise-anatomy)).
- **No roadmap language.** Describe what exists; never promise. The lint
  gate rejects `next release`, `coming soon`, `will be added`,
  `in a future`, `not yet built` (case-insensitive, prose only). Softer
  forms ("lands next", "later pass", "first pass") were also removed on
  sight. This was the second occurrence, which is why it is a gate.
- **Artifacts-only reporting.** Every claim in a report comes from a
  captured file; paste raw output once, never a summary of it. A unit
  report to the user includes: `make status` output, the generated blocks
  as generated, clone-run output, "gates caught" (what the gates found
  before the commit), and "decided alone" (judgment calls made without
  asking).
- **Four verify runs** per exercise (starter and solution, both tracks) on
  every change, recorded, and re-executed by `--target=ci`.
- **Floors bumped in the same commit** that lands a unit, set to the exact
  counts, after the gates ran green against the raised floors.
- **Reference reread before each lecture**, and the files reread recorded
  in `BUILD_PROGRESS.md` (gitignored build log). Reference material is
  `_reference/docs/en/lectures/<slug>/` (gitignored). Prose is always
  written fresh; unsourced figures from the reference are cut, never
  carried.
- **Sequential integration**: whole-tree `make status`, floors, and commit
  per unit, in order, by the integrating session only.
- **Fresh-clone verification** for every project unit (both tracks, from a
  temporary clone of the commit), pasted into the report.
- **Author identity**: commits carry only `Animesh Kumar
  <animesh.kcm@gmail.com>`; no Claude, AI, or Anthropic attribution in any
  committed content; push only on explicit instruction.
- **Declared markers** are the only escape hatches: `Starter-shape:
  non-code`, `Starter-divergence justification:`, `Corpus-divergence:
  <path> (<reason>)`, and the SPEC section headed literally
  `Seeded defects` (see "Decisions" below).
- **Contract evolution** is declared pre-1.0 in project 01's SPEC; every
  later project's delta table marks changed observations with
  **Breaking** rows; harness artifact sets only accrete across projects.
- **Evidence fields** in every committed `feature_list.json` are a real
  command plus its captured output, and a test re-executes each through
  the real CLI in a fresh workspace. README command fences are executed
  literally by a gate (`<!-- fence-exit: N -->` above a fence declares a
  non-zero exit).

## Subagent boundaries for lectures 07-14

- **May fan out**: one agent per lecture, writing only inside its own
  `lectures/lecture-NN-<slug>/` (demo `code/`, exercises, prose). At most
  three agents at once.
- **Never fans out**: `tools/`, `docs/glossary.md`, `docs/conventions.md`,
  `docs/curriculum-map.md`, `tools/expected_counts.json`, `library/`, any
  project, git commits, `.gitignore`, `build_state.json`,
  `BUILD_PROGRESS.md`, other lectures.
- Subagents do not commit, do not bump floors, do not touch shared files,
  do not run repo-wide writers (`gen_readme_blocks.py --write`, `make
  verify`, `make status`). They paste generated-block content by running
  the block's command themselves. They report their unit plus raw verify
  output. If one needs a shared-file change it reports and stops.
- Briefs are sourced from `docs/conventions.md` and `AGENTS.md`, never from
  a conversation. Each agent rereads its own reference material.
- Integration stays serial and belongs to the integrating session. A
  collision in a shared file means the boundary was wrong: report it, do
  not merge by hand.
- Batch one (07, 08, 09) produced no collision; the only cross-lecture
  effect was lecture 09 linking to lecture 08 in its prerequisites, which
  is an ordinary cross-link.

## Lectures 13 and 14: scope decision

- Keep the runnable demos but minimal. L13 is the loop-runner demo only:
  a goal file, a loop-state file, a deterministic fake maker and checker,
  a stopping condition, and a simulated timer (no wall clock). L14 is the
  stdlib-only graph-executor demo only: nodes, edges, shared state, a
  router, and exactly one rollback edge; no LangGraph or any dependency.
- One exercise each instead of two (so floors move by +1 exercise, not
  +2, for those units).
- Both READMEs link to an existing external repository for the
  production-scale implementations. **The user supplies that URL; it has
  not been supplied.** Until it is, the Further-exploration sections
  carry no such link and no sentence about one. Do not write a
  placeholder into committed content; the reminder lives in
  `BUILD_PROGRESS.md`.
- Projects 07 and 08 are out of scope; do not build or mention them.
- When 13 and 14 land, retitle the glossary section currently headed
  "Loop and graph vocabulary (lectures 13-14, later pass)" to drop the
  parenthetical qualifier.

## Per-lecture prompts (append to the brief)

Each prompt names the directory, the reference path, the exercise count,
the related-project sentence, and the behavioral shape of the demo.

- **Lecture 10** `lectures/lecture-10-why-end-to-end-testing-changes-results/`,
  reference `_reference/docs/en/lectures/lecture-10-why-end-to-end-testing-changes-results/`.
  Two exercises. Related project: Project 05 (its checker executes every
  feature's verification command against the running app instead of
  reading the code). Build on lecture 09 without repeating it: 09 is the
  premature claim caught by re-execution; 10 is why the kind of check
  matters, unit-level checks passing while the end-to-end path fails.
  Demo: a scripted session whose unit-level checks all pass ends
  differently (exit code and report) depending on whether the definition
  of done includes an end-to-end run against the assembled system.
- **Lecture 11** `lectures/lecture-11-why-observability-belongs-inside-the-harness/`,
  reference `_reference/docs/en/lectures/lecture-11-why-observability-belongs-inside-the-harness/`.
  Two exercises. Related-project sentence worded "The closest built
  project is Project 04" (structured event log `log/events.jsonl` with
  sequence numbers, `kb logs`, a guard that executes what the
  architecture doc claims); no project is dedicated to this lecture and
  none may be described as planned. Demo: a scripted session runs with
  and without a harness-written structured event log, and a second
  session that must diagnose or resume the first succeeds only when the
  log exists. Sequence numbers, never timestamps.
- **Lecture 12** `lectures/lecture-12-why-every-session-must-leave-a-clean-state/`,
  reference `_reference/docs/en/lectures/lecture-12-why-every-session-must-leave-a-clean-state/`.
  Two exercises. Related-project sentence worded "The closest built
  projects are Project 03 (session handoff and clean-state checklist) and
  Project 05 (rubric item five, clean-state, is `kb workspace-check`
  exiting 0)". Lecture 06 is the session start gate; this is the session
  end. Demo: a session ends dirty (partial work, stale progress note, a
  feature left in-progress without a handoff) versus clean, and the
  following session's observable outcome differs.
- **Lecture 13** `lectures/lecture-13-loop-engineering/`, reference
  `_reference/docs/en/lectures/lecture-13-loop-engineering/`. One
  exercise. No related-project sentence. Scope exactly as in the section
  above.
- **Lecture 14** `lectures/lecture-14-graph-engineering/`, reference
  `_reference/docs/en/lectures/lecture-14-graph-engineering/`. One
  exercise. No related-project sentence. Scope exactly as in the section
  above.

## Subagent brief (verbatim, used for lectures 07-09)

```text
# Lecture subagent brief (template; the lecture assignment is in your prompt)

You are building ONE lecture unit for the harness-engineering course at
<repo root>. Work ONLY inside lectures/<your-lecture-dir>/. Everything
else is read-only.

## Read first, in this order (before writing anything)
1. docs/conventions.md, in full. It is the standard you build to:
   directory shape, parity contract + normalization + semantic rules,
   verification contract, exercise anatomy incl. the genuine-partial
   standard and the acceptance-runs block, seeded defects, README
   section orders, command blocks, the behavioral-demo rule ("Lecture
   demos are behavioral"), mermaid rules, cross-links, the punctuation
   rule, AND the roadmap-language ban (lint-prose rejects "next
   release", "coming soon", "will be added", "in a future", "not yet
   built"; describe what exists).
2. AGENTS.md at the repo root (startup workflow, working rules).
3. Your reference material: _reference/docs/en/lectures/<your-slug>/index.md
   and any code under it. Recreate structure and concepts; write ALL
   prose fresh; never copy sentences; cut any figure or claim you cannot
   source or regenerate from committed fixtures.
4. Model units, as exemplars of the finished shape:
   lectures/lecture-09-why-agents-declare-victory-too-early/ (README +
   code/, the behavioral demo pattern), lecture 06 (the replay demo),
   lecture 04 (multi-run demo headings: per-run H3 with #### Python /
   #### TypeScript), and lecture 06's exercises/exercise-01-init-doctor/
   (full exercise anatomy incl. starter/solution both tracks, SPEC
   starter state, expected/starter-divergence.txt, verify.sh --target=ci).

## What you deliver (all inside your lecture dir)
- README.md with the ten H2 sections in the conventions' exact order.
- code/: the demo unit (SPEC.md, cases.json, fixtures/, expected/,
  python/main.py, typescript/main.ts, verify.sh copied+adapted from
  lecture 09's code/verify.sh, executable). The demo must be BEHAVIORAL
  where the lecture's claim is behavioral: something attempts the task
  under the claimed condition and observably fails (exit code +
  output); a metric may support the demo but cannot be it. Include a
  case where the failure occurs (annotate its README fence with
  <!-- fence-exit: N --> if non-zero) and one where it does not.
- exercises/ per your prompt's exercise count, each
  exercise-NN-<slug>/ complete: README (ten exercise sections), SPEC.md
  (incl. "Starter state" with the exact divergence signature),
  cases.json, fixtures/, expected/ incl. starter-divergence.txt,
  starter/{python,typescript}, solution/{python,typescript}, verify.sh
  (copy+adapt an existing exercise's, keeping --stack and
  --target=starter|solution|ci semantics and the 4-run ci mode).
  Starters are naive-but-real drafts with one realistic mistake whose
  first divergence is a VALUE mismatch naming the concept (never a
  formatting artifact, never null-vs-value; length diffs need the
  Starter-divergence justification: line). Include a trap fixture that
  catches exactly the naive mistake.

## Hard rules
- Dual-track byte-identical after normalization; stdlib only; no wall
  clock, no randomness, no network; deterministic everything.
- Demos and fixtures are self-contained in your dir. Never touch:
  tools/, docs/, library/, projects/, other lectures, any root file,
  git, build_state.json, BUILD_PROGRESS.md, expected_counts.json.
  If you find you NEED a change outside your dir (a shared rule, a
  normalizer gap, a floor), STOP and report the need instead of making
  it or working around it silently.
- Do not run repo-wide tools that write outside your dir (no
  gen_readme_blocks --write, no make verify/status, no git commands).
  Generated blocks in YOUR README: run the block's exact command
  yourself (from the repo root) and paste its stdout verbatim into the
  fenced block between the generated-block markers; integration
  re-verifies byte-match. The acceptance-runs block content comes from
  `uv run python tools/run_acceptance.py <your-exercise-dir>`.
- Command environment: prepend /opt/homebrew/opt/node@20/bin to PATH in
  your shell before pnpm/tsx commands, or invoke
  node_modules/.bin/tsx directly. Python via `uv run python ...` from
  the repo root. Per-unit conformance:
  `uv run python tools/conformance/runner.py --unit <your-unit-dir>`
  (and --stage starter for exercises).
- Lint what you wrote before reporting: `uv run ruff check <your-dir>`
  (100-column limit), `pnpm exec eslint <your ts files>`,
  `pnpm run typecheck`, `pnpm exec markdownlint-cli2 <your md files>`,
  shellcheck on your verify.sh files.
- External links: only URLs already linked elsewhere in this repo
  (check with grep) or the primary sources your reference page cites
  AFTER you fetch them and get a 2xx; report each URL with its status.
  No link may promise anything (roadmap ban).
- Cross-links out of your dir (relative links to docs/, other lectures,
  projects) are allowed and encouraged where conventions ask for them
  (Prerequisites, glossary terms). Related-project sentence in your
  Exercises section: use the wording given in your prompt; if your
  prompt says "no related-project sentence", omit it entirely.

## Definition of done + report
Before reporting, all of these must be green, run by you, output pasted
RAW in your report (no summaries):
1. `uv run python tools/conformance/runner.py --unit <lecture>/code`
2. `bash <lecture>/code/verify.sh` (both stacks)
3. For EACH exercise: `bash <exercise>/verify.sh --stack=both --target=ci`
4. `uv run python tools/lint/check_prose.py` outputs no error naming
   YOUR files (whole-tree output is fine; your files must be absent).
5. `uv run python tools/lint/check_structure.py` likewise: no error
   naming your files.
Your report: (a) unit path + one-paragraph design rationale (which
behavior the demo demonstrates and how); (b) the reference files you
reread; (c) raw outputs 1-3 above; (d) each exercise's starter
divergence signature + the one-line "what makes verify.sh flip to 0";
(e) URL list with statuses; (f) any shared-file need you hit (then you
stopped); (g) files you created (list).
```

## Open concerns, not closed

- **The kb `ask` contract.** `ask` changed shape across projects 01-03
  (keyword hits, then metadata, then chunk-grounded answers with a
  refusal path), each change declared under project 01's pre-1.0
  evolution rule with **Breaking** rows. Unsettled: whether `ask` should
  be frozen as a stable contract at some point (a 1.0 line the later
  projects must not break) or keep evolving per project. Current stance
  is "keep evolving, declare every break"; the user has not ruled.
- **TypeScript spawn cost.** The independent-evidence tests spawn one
  `tsx` process per evidence command (17 in project 05, with 240 s and
  900 s timeouts on the slow tests), and the TypeScript ladder replays
  three workruns. `make verify` wall time grows with every project;
  nothing caps it yet beyond the parallel runner.
- **Private-repo link exceptions.**
  [tools/lint/link_exceptions.json](tools/lint/link_exceptions.json)
  excuses two `github.com/ANI-IN/harness` URLs that 404 while the
  repository is private (with a `repo_public` removal trigger that fails
  the build once it is public and the entries remain) and an
  `openai.com` 403 that only excuses a 403 persisting across retries.
  Entries older than 30 days fail `lint-links` and must be re-dated or
  removed.
- **`gen_readme_blocks` cost.** Every generated block in every README is
  executed on each `make verify` (47 blocks at handoff, including the
  project 05 ladder, which replays three workruns). The worker pool
  helps; the cost still scales with content. No caching or change
  detection exists, by design (a cached block could drift silently).

## Decisions whose reasoning would otherwise be lost

- **GNU make 3.81 PATH resolution.** macOS ships make 3.81, which resolves
  bare recipe commands with the PATH it started with, so exporting PATH
  inside the Makefile does not make `pnpm` from `node@20` visible. The
  Makefile therefore resolves `$(NODE)` and `$(PNPM)` to absolute paths
  through `tools/find_node20.sh` and invokes them explicitly.
- **The node20 resolver** (`tools/find_node20.sh`) locates a Node 20
  binary (Homebrew `node@20`, then nvm, then PATH) so every gate runs the
  pinned major regardless of the learner's shell; project `verify.sh`
  scripts resolve `pnpm` softly through it so a Python-only learner is
  not blocked. `make setup TRACK=python|typescript|both` and
  `make doctor TRACK=...` exist for the same reason; Python and uv are
  required on every track because the verification machinery is Python.
- **Content sha over timestamps.** The kb chunk index stores a sha256 of
  each document's content (staleness is a content comparison) and the
  event log carries sequence numbers, never timestamps; evidence dates
  are the pinned build date `2026-08-27` (keep using it in new evidence
  and generated fixtures; do not introduce today's date). Rationale:
  byte-identical output across tracks and across runs is the parity
  contract, and any wall-clock value breaks it.
- **Subagents write directly into the tree** (no worktrees), which is why
  a batch must finish completely before any whole-tree gate runs: a
  half-written unit fails the structure and prose lints for reasons
  unrelated to the unit being integrated. Launch the next batch only
  after the previous batch's last commit.
- **The non-code starter shape marker.** An exercise whose starter is
  not code (a document the learner edits) declares `Starter-shape:
  non-code` in its SPEC.md; the structure lint accepts the missing
  `starter/{python,typescript}` only under that marker, with negative
  tests. Undeclared deviations from the exercise shape fail the gate.
- **Seeded-defect escape hatches.** A broken link or an invalid
  `feature_list.json` is allowed only in a fixture named in the unit
  SPEC's section headed literally `Seeded defects`; both the link lint
  and the feature-list schema test key on that heading, and a missing
  heading broke both escapes once during project 04 (which is the point).
- **Dedup mode.** `make status` runs `verify-dedup`, which skips each
  unit's own conformance run because the conformance gate already covers
  it; coverage equality (264 identifiers on both paths) is proven by
  `tools/test_dedup_coverage.py`. Exercise ci runs and project
  starter-must-fail gates never skip.
- **Canonical `kb` notation.** Project SPECs and evidence write commands
  as `kb <verb> ...`; each track expands it (documented in project 01's
  SPEC), and the apparatus runs canonical commands in-process while the
  conformance cases prove the real CLIs behave identically.

## Local files a fresh clone does not have

These are gitignored and exist only on this machine:

- `build_state.json`: `units` (per-unit status and evidence),
  `acceptance_runs` (per exercise key
  `<lecture-dir>/<exercise-dir>`: four entries `starter-python`,
  `starter-typescript`, `solution-python`, `solution-typescript`, each
  `{"exit": N, "ranAt": "YYYY-MM-DD"}` plus `"divergence"` for starters),
  and `starter_failure_messages` (per key: `{"python": ..., "typescript":
  ...}`). `tools/check_build_state.py` requires all four runs for every
  exercise in the tree when the file exists; when it is absent it passes
  and `--target=ci` carries the enforcement.
- `BUILD_PROGRESS.md`: the build log (session notes, reference files
  reread per unit, gates caught, the pending L13/L14 URL reminder).
- `_reference/`: the reference course the prose is rewritten from.
- The subagent brief lived in a session scratchpad; the copy above is the
  durable one.

## Commands

- Start: `make resume`, then `make setup`, `make doctor`, `make status`.
- Verify everything: `make status` (the commit gate); `make quick
  U=<unit-dir>` is the inner loop and never the gate.
- One unit's proofs: see step 1 of "Next best step".
- Fence count for the floor: the one-liner in step 3 of "Next best step".
