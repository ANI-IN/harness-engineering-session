# Assignment 1: Instructions. Specification: from one long instruction file to a map

The full requirements for [Assignment 1](README.md). The README gives the story and the steps; this
page is the reference you check your work against.

> **Terms on this page**
>
> - **Work folder**: The folder you submit; `section-1-instructions/assignment/starter/` unless you pass `A1_WORK=` to make.
> - **Tree**: Your `instructions/` folder; the harness layer copies it over the TeamTrack workspace root.
> - **Rule tag**: An id such as `R1.2` or `CV-07` that marks one rule in the original file.
> - **Overlap**: The share of the original rule's content words that a rewritten rule keeps.
> - **Score record**: The file the referee writes for each run, with every measured result.
> - **Bare arm**: An agent run with the ticket and the repository, and no harness.
> - **Harness arm**: The same run with the harness turned on.
> - **Live evidence**: The files your real A/B run wrote, collected into `live/`.
> - **Experiment export**: The JSON file the run writes for each arm, listing that arm's runs.
> - **LangSmith**: The tracing service that records every model call of a run.

> Your output will differ: the examples on this page come from the course's own starter and reference
> work, not from your files.

## Inputs

- `starter/original/AGENTS.md`: the 899-line file. Read-only: the grader pins its hash and grades
  rule coverage against the unchanged file only.
- `platform/teamtrack/`: the product. Your tree lands on the TeamTrack workspace root, so a link in
  your tree may point to a TeamTrack file (for example `docs/features/f1.md`) as if both were one
  folder.

## Files you must produce

Outputs, all in your work folder: `instructions/`, `checker/check_docs.py` with at least one test file
of your own, `ab-report.md`, and `live/`.

The layout, with the required files and a suggested split:

```text
section-1-instructions/assignment/starter/   your work folder
  original/AGENTS.md                  the 899-line input (read-only)
  instructions/
    AGENTS.md                         the map, 30 to 120 lines
    ARCHITECTURE.md                   layering rule (R6), wiring, board, configuration
    docs/
      SECURITY.md                     tenant isolation (R1), roles (R2)
      RELIABILITY.md                  safe retries (R4), audit log (R5), migrations (R7)
      QUALITY_SCORE.md                grades, testing, the legacy API
      PLANS.md                        roadmap, scope
      design-docs/index.md            catalogue of design docs
      design-docs/<your docs>.md      for example API conventions (R3), history
      product-specs/index.md          product behaviour and pointers to docs/features/
      product-specs/<your docs>.md
    .agents/skills/<name>/
      SKILL.md                        built from the skill template
      references/...                  optional, one level deep
  checker/
    check_docs.py                     your checker
    test_check_docs.py                the visible tests (do not edit)
    test_<yours>.py                   your tests
  ab-report.md                        the filled report
  live/                               the live evidence (collected by live_evidence.py)
```

The split beyond the required files is a suggestion. Another split is fine if every rule has one home
an agent would find from the map.

## Requirements

### The tree

- **R-T1.** The required files under "Files you must produce" exist. `AGENTS.md` has 30 to 120 lines.
- **R-T2.** `AGENTS.md` defines no rule. It points to where each rule lives and may mention ids as
  references.
- **R-T3.** Every active tagged rule of the original is defined exactly once, as `[ID]` followed by
  its statement. The statement keeps at least half of the original's content words (see "Overlap").
  Reword freely within that limit.
- **R-T4.** Retired rules are not defined anywhere. You may mention them as history.
- **R-T5.** Every `.md` and `.txt` file in the tree can be reached from `AGENTS.md` by following
  Markdown links or path-like code spans, in any number of steps.
- **R-T6.** No tree file has the same relative path as a TeamTrack file (for example
  `docs/HANDBOOK.md`). The layer would overwrite it, and the bare arm reads `docs/HANDBOOK.md`.
- **R-T7.** No new facts. Every inline code span in the tree appears in the original (ignoring case,
  backticks, and runs of whitespace) or is a path that exists in the tree or in TeamTrack. This keeps
  the A/B fair: the harness may reorganise knowledge, never add facts the bare arm cannot read.
- **R-T8.** Your checker exits 0 on your tree.

### The skill

- **R-S1.** Exactly one folder in `instructions/.agents/skills/`, copied from
  `use-in-your-repo/skills/skill-template` and renamed. `name` equals the folder name and is not
  `skill-template`.
- **R-S2.** `uv run shipharness skills validate instructions/.agents/skills` reports no errors and no
  warnings (body under 500 lines, references one level deep and present).
- **R-S3.** The description says what the skill does and contains "Use when".
- **R-S4.** The body keeps the template's sections `## When to use`, `## Steps`, and
  `## Checks before you finish`, with no `<Placeholder>` text left.
- **R-S5.** `AGENTS.md` points to `.agents/skills/<name>/SKILL.md`, and the steps cite the rule tags
  they serve. The section-1 tasks add an org-wide list, so a list-endpoint skill fits.

The format rules come from the [Agent Skills Specification](https://agentskills.io/specification).

### The checker

Command:

```text
uv run python <work>/checker/check_docs.py --original <file> --tree <dir> [--product <dir>]
```

`--product` defaults to `platform/teamtrack`. Keep the function names and signatures in the starter
file: the visible tests import them, and the grader also runs the file as a command.

Output: one line per problem, `ERROR <kind> <key> [<detail>]`, then one summary line. On success:
`OK: <files> files, <links> links, <rules> rules covered`, exit 0. Otherwise `FAILED: <n> problems`,
exit 1. A missing `--original` or `--tree` path prints `ERROR usage --<name> not found: <path>` and
exits 2. Paths in output are relative to the tree, with `/`. Line numbers start at 1.

Which text is scanned: every `*.md` file under the tree, in plain string order of its tree-relative
path. Lines inside fenced code blocks (opened and closed by a line starting with three backticks or
`~~~`) are ignored for links, paths, and rules. Inline code spans are ignored for links and rule tags.

| Kind | Key | Detail | When |
|---|---|---|---|
| `broken-link` | `file:line` | target as written | A link, image, or reference whose target is missing or outside the tree |
| `broken-anchor` | `file:line` | target as written | The target is an existing `.md` file with no heading for that anchor |
| `broken-path` | `file:line` | the code span | A path-like code span that resolves nowhere |
| `missing-rule` | the id | none | An active rule of the original is not defined in the tree |
| `weak-rule` | the id | `file:line overlap=0.NN` | The first definition keeps less than half of the original's content words |
| `duplicate-rule` | the id | `file:line` | A second or later definition of an id (one line per extra definition) |
| `retired-rule` | the id | `file:line` | A retired rule is defined in the tree |
| `unknown-rule` | the id | `file:line` | A definition or reference of an id the original does not have |
| `rule-in-map` | the id | `file:line` | A definition in the tree's root `AGENTS.md` (it still counts as defined) |

**Links.** Targets with a scheme (`https:`, `mailto:`) are not checked. A target in `<...>` is taken
without the brackets; otherwise it ends at the first space, so a title such as `"Security"` is
dropped. `%20` and other escapes are decoded. A target resolves relative to the linking file's folder
and must stay inside the tree; a target that starts with `/` counts as outside. It exists if the path exists in the tree or, failing that, at the same
relative path under `--product`. Directories count.

**Anchors.** Checked only when the target is a `.md` file; `#part` alone means the same file. Anchors
follow GitHub: take the heading text, trim it, lowercase it, remove backticks and asterisks, remove
every character that is not a letter, digit, space, hyphen, or underscore, and turn each space into a
hyphen. A repeated heading gets `-1`, `-2`, and so on, in order.

**Path-like code spans.** An inline code span made only of letters, digits, `_`, `.`, `-` and `/`, not
starting with `/`, that contains a `/` or ends in `.md`, `.txt`, `.py`, `.toml`, `.ini`, `.json`,
`.sh`, `.html`, or `.css`. It exists if it resolves, as a whole or relative to the file's folder, in
the tree or under `--product`. A span ending in `/` must be a directory. Commands such as
`python -m pytest tests/visible -q` and endpoints such as `GET /v1/issues` are not paths.

**Rules.** An id is `R<1-9>.<n>` or `CV-<two digits>`. A definition is `[ID]` not followed by `(` or
`[`, so `[R2.1](docs/SECURITY.md)` is a link. Every other occurrence of an id, or of a family such as
`R1`, is a reference. The statement of a definition is the text after the tag, up to the next tag on
the same line. When the tag is the last one on its line, the statement continues on the next lines
until a blank line, a list item (`-`, `*`, `+`, `1.`), a heading, a table row (`|`), a fence, or a line
with another definition. A definition is retired when its statement starts with `(retired`. Unknown
means a full id the original does not define, or a family `R<n>` with no `R<n>.x` in the original.

### Overlap

- Content words of a statement: remove ids, lowercase, split on every character outside `a-z`, `0-9`
  and `_`, then drop the words in the starter's `STOPWORDS` (common words such as "the" and "of") and words
  shorter than two characters.
- overlap = |words(original) ∩ words(new)| / |words(original)|, or 1.0 when the original has no
  content words. A first definition below 0.5 is `weak-rule`.

Example. A tree with one file, `docs/SECURITY.md`:

```text
- [R1.1] Every query on customer data filters by the caller's `org_id`.
See [the old notes](OLD.md).
- [R1.2] Unrelated words entirely.
```

The course's reference checker prints (64 `missing-rule` lines cut to three, `...` marks the cut):

```text
ERROR broken-link docs/SECURITY.md:2 OLD.md
ERROR missing-rule CV-22
...
ERROR missing-rule CV-01
ERROR weak-rule R1.1 docs/SECURITY.md:1 overlap=0.41
ERROR weak-rule R1.2 docs/SECURITY.md:3 overlap=0.00
ERROR missing-rule R1.3
...
FAILED: 67 problems
```

`R1.1` is weak although its first sentence is copied word for word. The original goes on
("Repositories take `org_id` as an explicit argument and filter on it; ..."), and the copy keeps 41%
of its content words.

### The A/B report

`ab-report.md` keeps the template's six sections and has no to-do marker left.

- **Setup**: the exact command (with `--split section-1`, `--k 3`, `--layers instructions`, and a
  `--batch` label), `Instructions tree commit: <sha>`, and `Runs per arm: <n>`.
- **Results**: an `R1` row (House rule 1: Tenant isolation) and an `R3` row (House rule 3: API conventions),
  with `failing/runs` per arm (for example `3/24`). Runs equal "Runs per arm". No percentages.
- **Links**: the two LangSmith experiment URLs.
- **Cost and traces**: `Cost: $<x>` at most 2.50 and `Traces: <n>` at most 150.
- **Reading the result**: at least 60 words that discuss both rules, `R1` and `R3`. **Limits**: at
  least 20 words.
- The command, runs per arm, `R1` and `R3` counts, and links equal what the live evidence says (R-L5).

## Self-check

| What | Command |
|---|---|
| Your checker | `uv run python section-1-instructions/assignment/starter/checker/check_docs.py --original section-1-instructions/assignment/starter/original/AGENTS.md --tree section-1-instructions/assignment/starter/instructions` |
| Your tests | `uv run python -m pytest -q -p no:cacheprovider section-1-instructions/assignment/starter/checker` |
| The skill validator | `uv run shipharness skills validate section-1-instructions/assignment/starter/instructions/.agents/skills` |
| The self-check | `make check-assignment-1` (another folder: `make check-assignment-1 A1_WORK=<dir>`) |

On a finished work folder, every self-check line is PASS, the checker prints `OK: ...` on your tree,
and the grader prints each criterion with its points and `Score: <n>/100`.

### Grading criteria, item by item

"Visible" items are checked by `make check-assignment-1`; "hidden" items only by the grader.
"Scaled" items earn their points in proportion to the share of active rules you covered, so an empty
tree earns nothing for having no duplicates.

| Criterion | Item | Points | Checked |
|---|---|---|---|
| A (15) | Required files present (proportional) | 5 | visible |
| | `AGENTS.md` between 30 and 120 lines, no stub left | 3 | visible |
| | Every doc reachable from the map (proportional; needs half the layout) | 4 | visible |
| | No TeamTrack file overwritten (needs half the layout) | 3 | visible |
| B (25) | Original unchanged (scaled) | 2 | hidden |
| | Active rules defined with overlap at least 0.5 (proportional) | 12 | hidden |
| | No duplicate definitions (scaled) | 2 | hidden |
| | No retired rule defined (scaled) | 2 | hidden |
| | No unknown ids (scaled) | 2 | hidden |
| | No definition in `AGENTS.md` (scaled) | 2 | hidden |
| | No new facts: 1 point off per unknown code span (scaled) | 3 | visible |
| C (12) | Validator: no errors, no warnings, exactly one skill | 4 | visible |
| | Name equals the folder; "Use when" in the description | 2 | visible |
| | Template sections kept, no placeholders | 2 | visible |
| | Linked from `AGENTS.md` | 2 | visible |
| | Steps cite rule tags | 2 | visible |
| D (26) | The unchanged visible tests pass (proportional) | 6 | hidden |
| | Your own tests pass | 2 | visible |
| | Exits 0 on your tree (needs your tests passing) | 2 | visible |
| | Reference tree: no false alarms (3) and 3 injected faults found (1 each) | 6 | hidden |
| | Eleven hidden cases (proportional) | 10 | hidden |
| E (10) | Six sections, no to-do marker left | 2 | visible |
| | Exact command (1); tree commit and runs per arm (1) | 2 | visible |
| | `R1` and `R3` rows as counts matching runs per arm (1 each) | 2 | visible |
| | Two LangSmith experiment links | 1 | visible |
| | Cost and traces within budget | 1 | visible |
| | Reading (60 words, `R1` and `R3`) and limits (20 words), 1 each | 2 | visible |
| F (12) | R-L1: `live/` present and well formed; without it every F item scores 0 | 3 | visible |
| | R-L2: consistent with the command (four parts, proportional) | 3 | visible |
| | R-L3: class model and caps (five parts, proportional) | 2 | visible |
| | R-L4: every harness run log placed your submitted tree | 2 | visible |
| | R-L5: report values equal the evidence (five parts, proportional) | 2 | visible |

## Evidence to hand in

You run the A/B once, live, with the course model (`gpt-6-luna`), through the real runner and the
Docker sandbox, with the class caps ($0.20 per arm per run, $0.04 per review, $2.50 per command).
`live_evidence.py` copies what the run wrote into `live/`:

| Path | What it is | Written by the run to |
|---|---|---|
| `live/output.txt` | First line `$ <the exact command>`, then everything it printed, ending with its `Cost: $...` line | your terminal |
| `live/experiments/<name>.json` | The two experiment exports, one per arm | `exports/experiments/` |
| `live/scores/<run_id>.json` | The score record of every run in the exports | `exports/scores/` |
| `live/runs/<run_id>/events.jsonl` | The run log of every harness-arm run | `.shipharness/runs/` |

The self-check and the grader read these files only. They never re-run a model and need no keys.

- **R-L1.** Every file above is present and well formed: score files validate with every field
  present, run log lines validate as events, the exports name one bare and one harness experiment,
  and `output.txt` has the command line and the cost line.
- **R-L2.** The run matches the command: `--split section-1`, `--k 3`, `--layers instructions`, a
  `--batch` label, no `--from-working-tree`. Both exports carry that split, k, and batch. Every run id
  in an export has its score file, with the export's arm and layers, a `checkpoint_sha` equal to the
  export's commit for that checkpoint, and a `section-1` task. Each arm has 3 runs of each of the 8
  tasks (24).
- **R-L3.** Class model and caps: `gpt-6-luna` in both exports and every harness run log, `recorded`
  false, `sandboxed` true, no run above $0.20 or review above $0.04, and a cost line of at most $2.50
  that names `gpt-6-luna`.
- **R-L4.** The harness arm used your tree. The layer writes a note to each run log, "placed N
  instruction files", listing the files it copied. In every harness run log that list must equal the
  files of the tree you submit. Adding or removing a tree file after the run breaks the match, and
  re-running is not allowed.
- **R-L5.** `ab-report.md` agrees with the evidence.

### Run the A/B

Needs keys and Docker; at most $2.50. Run from the repository root, and replace `<name>` with a short
label of your own, such as your initials:

```bash
git switch -c a1-ab-run                          # throwaway branch: never merge it
rm -rf platform/teamtrack/harness/instructions
cp -r section-1-instructions/assignment/starter/instructions platform/teamtrack/harness/instructions
git add platform/teamtrack/harness/instructions && git commit -m "Assignment 1: my instructions tree for the A/B"
git log -1 --format=%h                           # the "Instructions tree commit"
CMD="uv run shipharness experiments --split section-1 --k 3 --layers instructions --batch a1-<name>"
echo "\$ $CMD" > ~/a1-live-output.txt            # the exact command: first line of the evidence
$CMD | tee -a ~/a1-live-output.txt               # the live run; it ends with "Cost: $..."
git switch -                                     # back to your work branch
uv run python section-1-instructions/assignment/live_evidence.py --batch a1-<name> --output ~/a1-live-output.txt
uv run python section-1-instructions/assignment/ab_summary.py --batch a1-<name> --exports section-1-instructions/assignment/starter/live
```

The layer reads its tree from `platform/teamtrack/harness/instructions/`, so the copy is what the
harness arm gets. The bare arm reads `docs/HANDBOOK.md` as always. The course's own unit tests for that
folder fail on the throwaway branch; that is expected. `exports/` and `.shipharness/` are not
committed, so they are still there after `git switch -`. Pass `--work <dir>` to `live_evidence.py` for
another work folder. Commit `live/` with your work.

## Limits

- Write only inside your work folder. Do not edit `original/AGENTS.md`, `platform/teamtrack/`, or
  `platform/src/`, except for the temporary copy above, on a throwaway branch.
- The checker uses only the Python standard library.
- One A/B command, within the budget. Every run is a dot: never drop runs or re-run for a nicer
  result.

### Cost and trace budget

| Step | OpenAI | LangSmith traces |
|---|---|---|
| Self-check, checker, validator, `ab_summary.py`, `live_evidence.py` | $0 | 0 |
| The live A/B: 8 tasks x 2 arms x 3 runs = 48 runs | At most $2.50; the command stops cleanly at its cost cap | 2 per run (agent and referee): 96, within 150 |

For scale: in the test runs before class, single arm runs on the org-wide issue search cost between
$0.0051 and $0.0151 each ([evidence](../../docs/evidence/s1.md#s1-pilot)).

### Common mistakes

- Pasting the whole original into `docs/` with a short map on top. `rule-in-map` and
  `duplicate-rule` appear as soon as two copies exist, and the retired rules come along.
- Rewriting rules until they say something else. The overlap check is a floor: a rule that drops
  "never 403" has changed meaning even if it reads well.
- Adding helpful facts that are not in the original. The bare arm cannot read them (R-T7).
- Links written from the repository root inside `docs/`. From `docs/SECURITY.md`,
  `[x](docs/RELIABILITY.md)` points to `docs/docs/RELIABILITY.md`.
- Putting `docs/HANDBOOK.md` or a copy of `docs/features/` into the tree.
- Running the A/B with the course's own tree still in place, or adding a document after the run:
  `live-tree` fails.
- Typing the report's numbers by hand. Copy them from `ab_summary.py --exports <work>/live`.
- Committing only `ab-report.md`. Without `live/`, criterion F scores 0.

## Sources

- Source 1: Agent Skills Specification, <https://agentskills.io/specification>, Agent Skills project, n.d.
