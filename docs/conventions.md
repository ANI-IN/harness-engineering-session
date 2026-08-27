# Conventions

Every folder in this repository follows the standard on this page. The rules
here are not style preferences. Each one exists because the [reference
course](https://github.com/walkinglabs/learn-harness-engineering) this
curriculum was modeled on demonstrably rotted where the rule was missing:
broken run commands, three incompatible template dialects, dead links, and
starters that did not compile. Most rules are machine-enforced by
`make lint-structure`, `make lint-links`, and `make lint-mermaid`; this page is
the human-readable statement of what those tools check.

## Naming and numbering

- Curriculum units: `lecture-NN-<slug>`, `exercise-NN-<slug>`, `project-NN-<slug>`.
  `NN` is always two digits (`01`, not `1`), including in prose and headings.
- Slugs are lowercase kebab-case, derived from the title.
- Agent-facing entry files use their ecosystem-canonical uppercase names:
  `AGENTS.md`, `CLAUDE.md`, `SPEC.md`, `README.md`, `SKILL.md`.
- Human-facing documents and scripts are kebab-case: `session-handoff.md`,
  `clean-state-checklist.md`, `verify.sh`.
- Machine-readable state keeps its course-canonical name `feature_list.json`
  (snake_case: it is a harness artifact with a fixed name, taught as such).
- Python sources are snake_case, TypeScript sources are kebab-case; each track
  follows its own ecosystem inside its own tree.

## Directory shape of a runnable unit

Every unit that has runnable code (a lecture demo, an exercise, a project)
uses one shape:

```text
<unit>/
  SPEC.md              # the shared contract both tracks implement
  cases.json           # machine-readable conformance cases (see below)
  fixtures/            # shared inputs
  expected/            # shared expected outputs - the grading authority
  python/              # Python implementation (plain source tree)
  typescript/          # TypeScript implementation (plain source tree)
  verify.sh            # runs one or both tracks; --stack=python|typescript|both
```

Exercises replace the two implementation dirs with
`starter/{python,typescript}/` and `solution/{python,typescript}/`; the
conformance runner executes the **solution**, `verify.sh` exercises both.

Projects whose starter is an experimental condition rather than a partial
implementation (project 01's starter is a task prompt, by design) keep a
complete `solution/{python,typescript}/` next to that non-code `starter/`;
the conformance runner still executes the solution stage. This shape must
be declared by a `Starter-shape: non-code` line in that project's SPEC.md;
`lint-structure` never infers it from missing directories, so a project
that merely forgot a starter track (or one of its two starter stacks) is
an error, and declaring the marker while shipping starter code is too. Projects may also
carry `harness/` (language-neutral harness artifacts) and per-track
`tests/` inside each solution, run by `make verify`.

There is no other layout. A file that exists in one track and not the
other must be explained by a line in that unit's SPEC.md.

## Workspace shape (single root toolchain)

Unit directories contain **no** `pyproject.toml`, `package.json`, or
`tsconfig.json`. There is exactly one Python project (the repo root, managed by
uv) and one TypeScript project (the repo root, managed by pnpm):

- Python code runs as `uv run python <unit>/python/main.py` and unit tests run
  as `uv run pytest <unit>/python/tests` from the repo root.
- TypeScript code runs as `pnpm exec tsx <unit>/typescript/main.ts` and unit
  tests are picked up by the root vitest config
  (`**/typescript/**/*.test.ts`).

> **Deviation from the original build brief.** The brief sketched per-unit
> manifests and uv/pnpm workspaces. With ~40 runnable units, per-unit manifests
> mean ~80 dependency files that must stay in lockstep, exactly the
> hand-propagated duplication that let the reference's 14 app copies drift
> (one had a one-character difference; nine did not compile). A single root
> toolchain makes version pins one-place-only and keeps unit directories pure
> source. The cost (units cannot pin private dependencies) is no cost here,
> because curriculum code is standard-library-only by design.

## The parity contract

One spec, one verification suite, two implementations.

- SPEC.md states: the CLI surface (arguments, flags, stdin/stdout shape), the
  exact exit codes and their meanings, the files read and written with their
  schemas, and the expected output referencing files in `expected/`.
- Both implementations must produce **byte-identical observable output after
  normalization** for the same input: same stdout, same exit codes, same
  written artifacts.
- `tools/conformance/runner.py` executes every case in `cases.json` against
  both tracks and diffs three ways: python vs `expected/`, typescript vs
  `expected/`, python vs typescript. Any post-normalization divergence fails
  the build: it is a failing test, not a cosmetic inconsistency.

### Normalization (the definition of "byte-identical")

Raw byte equality across two language runtimes is not achievable (line
endings, JSON key order, float repr, path separators). Conformance therefore
compares outputs after the normalization pass defined in
`tools/conformance/normalize.py`, which is part of this contract:

1. CRLF/CR line endings become LF.
2. Trailing whitespace is stripped from every line.
3. Output ends with exactly one newline (empty stays empty).
4. JSON payloads are re-serialized canonically: sorted keys, 2-space indent.
5. Path separators normalize to POSIX `/` (in text and inside JSON strings).
6. Floats inside JSON round-trip through canonical serialization, and
   integral floats unify with integers (Python's `1.0` and JavaScript's `1`
   are the same JSON number, per RFC 8785 semantics); floats in plain text
   must be explicitly formatted by the unit per its SPEC.md.
7. Canonical JSON emits literal UTF-8: Python's default `ensure_ascii`
   escaping and TypeScript's literal output normalize to the same bytes.

**Any divergence the normalizer cannot absorb is a spec bug in the unit, never
a runner setting.** If two tracks disagree after normalization, the spec is
under-specified: tighten SPEC.md and fix the implementations.

### Semantic rules the normalizer cannot carry (SPEC.md obligations)

Three divergence classes are about behavior, not formatting. The normalizer
does not touch them; every SPEC.md inherits these rules and implementations
must obey them (the conformance canary demonstrates all three):

- **stderr is diagnostics only.** The observable contract is stdout, exit
  codes, and written files. stderr is never asserted and never compared;
  anything that must match goes to stdout or a file.
- **Input line endings are the implementation's job.** The normalizer
  applies to outputs only. Fixture inputs may deliberately contain CRLF;
  implementations treat LF and CRLF alike as line separators (Python text
  mode does this automatically; TypeScript must split on `/\r?\n/`).
- **String lengths count Unicode code points**, not UTF-16 code units.
  `mega🚀rocket` has length 11. TypeScript implementations use code-point
  iteration (`[...str].length`), never `String.length`, wherever a SPEC
  involves lengths or indexing.

## The verification contract

Every `verify.sh`, and every conformance run:

- accepts `--stack=python|typescript|both` (default `both`);
- exits `0` on success and non-zero on failure; no other signal counts;
- prints what it checked and for which stack;
- needs **no network** after `make setup`;
- writes nothing outside its own unit directory or a temp directory;
- is deterministic: injected clocks, fixed seeds, and the deterministic fake
  agent replace time, randomness, and model calls.

Exercise `verify.sh` scripts additionally accept
`--target=starter|solution|ci` (default `starter`, the learner's workspace):
`starter` and `solution` check that stage's implementation against
`expected/`; `ci` asserts the repo invariant instead (the pristine starter
fails for its intended reason AND the solution passes). The repo-level
verify loop (`tools/run_verify.py`) calls exercise scripts with
`--target=ci`.

### Full matrix, dedup mode, and the inner loop

The conformance runner executes units in a worker pool but prints reports
in discovery order, so output and failure positions are deterministic
regardless of completion order. `make verify` is always the full matrix.
`make status` runs `verify-dedup` instead: scripts whose only work is a
solution-stage conformance run (lecture demos, the canary, and the
projects' solution runs plus their own test-suite sub-runs) honor
`HARNESS_SKIP_UNIT_CONFORMANCE` and skip what the status run's
conformance gate and root test suites perform themselves. Exercise
`--target=ci` acceptance runs and the projects' starter-must-fail gates
never skip. Coverage equality is not assumed: the runner logs every
executed `(unit, stage, stack, case)` identifier when
`HARNESS_COVERAGE_LOG` is set, and `tools/test_dedup_coverage.py` fails
the build if the deduplicated path could ever cover fewer cases than the
full one. `make quick U=<unit-dir>` (doctor plus that unit's `verify.sh`)
is the inner loop only; the commit gate remains `make status`.

### Fail-on-empty floors

`tools/expected_counts.json` records the minimum number of conformance
units, verify scripts, lectures, exercises, and projects the tree must
contain. Discovery reporting fewer is a build failure, so a broken glob can
never look like success. **The commit that lands a unit must bump the
relevant floors in the same commit, and a unit is not done until
`make conformance` and `make verify` have been run green with the raised
floors.**

## Exercise anatomy

- `starter/` runs, but fails `verify.sh`, and it must fail **for the intended
  reason only**. A starter failing on an import error or a missing file is a
  build bug. The failure message names the work to do and where.
- `solution/` is complete, idiomatic in each track, and passes `verify.sh`.
- The shared `fixtures/` and `expected/` files are the grading authority: the
  same expected outputs grade both tracks with no duplicated test logic.
- Every exercise must be completable only by modifying code: if a learner
  could "finish" it by writing prose or a prompt, the exercise is misdesigned.
- Acceptance for every exercise, every time: four runs, starter and solution,
  in both tracks. Starter fails twice for the right reason; solution passes twice.
- The four runs are enforced, not remembered: every exercise commits its
  starter's exact failure signature in `expected/starter-divergence.txt`,
  and `verify.sh --target=ci` (run by `make verify`) performs the four runs
  individually, requiring each starter run to fail with exactly that
  signature and each solution run to pass. The build session additionally
  records all four runs per exercise in `build_state.json`
  (`tools/check_build_state.py` fails when any are missing).
- **The genuine-partial standard** (machine-checked by `lint-structure`
  against the committed divergence signature): a starter must be a partial
  *implementation*, not a stub, so its first divergence must be a value
  mismatch inside a populated structure, and the mismatch must change
  content. A null-vs-value divergence reads as "not implemented" and is
  rejected outright. A formatting-only divergence (two strings identical
  once every non-alphanumeric character is removed, such as a markdown
  bullet prefix or collapsed whitespace) makes the learner debug
  punctuation instead of the exercise's concept and is rejected the same
  way; the rule covers quoted strings only, since a numeric sign flip like
  `-2 != 2` is content. A structural divergence (a `length N != M` diff, a
  missing or unexpected key) and a formatting divergence in an exercise
  that is genuinely about formatting are accepted only when the exercise's
  SPEC.md carries a one-line justification starting with
  `Starter-divergence justification:` explaining why that signal is the
  right one for that exercise. The working test: the first divergence
  should name the concept (a dropped section, a wrong classification, a
  missing pin), never a formatting artifact. Prefer naive first drafts
  with one realistic mistake each, plus fixtures that trap exactly those
  mistakes.
- Hints are progressive `<details>` blocks so they do not spoil on sight.

## Seeded defects

When a fixture is deliberately broken (a bug the learner must find or a
failure a tool must catch), the unit's SPEC.md states:

1. the **exact observable symptom** (message, wrong value, exit code), and
2. **which stage catches it** (which check, test layer, or tool).

Both tracks must reproduce the *same* failure, not two different failures.

## README anatomy

Every directory under `lectures/`, `projects/`, `skills/`, `library/`, and
`tools/` has a `README.md`. No orphan folders. Section orders are fixed and
machine-checked:

- **Lecture README** (H2s, in order): Learning objectives · Prerequisites ·
  The problem · Concepts · Architecture · Demo · Implementation notes · Key
  takeaways · Exercises · Further exploration. (The H1 + opening paragraph
  carry the title and the lecture's single defended claim.)
- **Project README**: Overview · Learning objectives · Prerequisites ·
  Architecture · Project structure · Setup · Usage · Demo flow · Testing and
  validation · Expected output · Troubleshooting · Extension challenges ·
  Related lectures.
- **Exercise README**: Objective · Why this matters · Prerequisites ·
  Provided · Your task · Expected outcome · How to verify · Hints · Solution
  walkthrough · Acceptance runs (a generated block running
  `tools/run_acceptance.py` on the exercise, so the published four-run
  transcript is produced by execution, never written by hand).

## Command blocks

Everywhere commands are shown, Python comes first, then TypeScript, with the
same two headings every time:

```text
### Python
### TypeScript
```

Never show only one track. The only exceptions are the declared single-track
units (`tools/`, `skills/harness-creator/scripts/`), which say so in one
sentence, and ecosystem-specific notes, which are labeled as such.

## Mermaid diagrams

- Every lecture and project README has at least one diagram that adds
  information the prose does not already state.
- Pick the type from the content: `flowchart LR` for pipelines and data flow,
  `sequenceDiagram` for agent/tool interaction over time, `stateDiagram-v2`
  for lifecycles and state machines (feature statuses, session lifecycle).
- No theme-dependent styling: no `classDef`, no hardcoded colors.
- Every block must parse (`make lint-mermaid`).

## Cross-links

- Relative paths only; never absolute GitHub URLs for in-repo content.
- Every lecture links forward to its exercises and its related project; every
  project links back to its lectures; every library template links to the
  lecture that motivates it.
- `make lint-links` verifies every relative link and anchor;
  `make lint-links-external` fetches external URLs (up to 3 attempts each)
  and runs before a lecture is committed. A URL that does not resolve is
  removed, not marked dead.
- A URL that is live for humans but blocked for automated fetchers may be
  excused only via `tools/lint/link_exceptions.json`. Every entry carries
  the expected status, a reason, its date added, and a removal trigger.
  Entries expire: older than 30 days fails `lint-links` until re-verified
  and re-dated or removed, and machine-checkable triggers (such as a
  private repository becoming public) are probed by the external check and
  fail the build once the justification no longer holds.

## Punctuation

No em-dashes (U+2014) and no en-dashes (U+2013) anywhere in markdown prose.
Use a comma, a colon, a normal hyphen (hyphen-minus, ASCII 45), or restructure
the sentence; a hyphen doing an em-dash's job usually reads worse than a
comma or a full stop, so prefer rewriting. Number ranges use a plain hyphen
(lectures 01-06).

This applies to every shipped .md file: READMEs, SPEC.md files, lecture
bodies, docs/, library templates, and the text of mermaid node labels. It
also applies to commit messages. It does NOT apply to: source code under
`python/` and `typescript/`, code fences and inline code spans, anything
under `fixtures/` or `expected/` (expected output is the grading authority
and is never edited for style), or URLs.

Enforced by `make lint-prose`, which runs as part of `make lint` and CI.

## Terminology and claims

- `docs/glossary.md` is authoritative: one term per concept, defined once.
  Notable fixed choices: feature statuses are
  `not-started | in-progress | blocked | passing`; the progress log is
  `claude-progress.md`; the feature list is `feature_list.json` validated by
  `library/templates/feature_list.schema.json`.
- Every claim about agent behavior is (a) demonstrated by a runnable demo,
  (b) cited to a primary source, or (c) explicitly framed as a design
  heuristic. Invented benchmark numbers are forbidden.
- **No figure appears in prose unless it is produced by a committed fixture
  and regenerated by `make verify`.** Two mechanisms carry this: generated
  output blocks (`<!-- generated-block: <command> -->` around a fenced
  block; `tools/gen_readme_blocks.py --check` runs in `make verify` and
  fails on drift, `--write` regenerates) and, for exercises, the recorded
  starter divergence (`expected/starter-divergence.txt`) that the ci target
  re-asserts on every run. A number quoted from an external source carries
  its Source line instead.
