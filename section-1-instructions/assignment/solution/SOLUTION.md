# Assignment 1: Instructions. Solution: from one long instruction file to a map

This folder holds a finished work folder for [Assignment 1](../README.md): the instructions tree, the
checker with its tests, the A/B report, the live evidence, and the captured checks. This page explains
how it was built and why.

> **Terms on this page**
>
> - **Map**: A short `AGENTS.md` that says where each rule lives, instead of holding every rule.
> - **Rule tag**: An id such as `R1.2` or `CV-07` that marks one rule in the original file.
> - **Overlap**: The share of the original rule's content words that a rewritten rule keeps.
> - **Workspace overlay**: The harness layer copies the tree on top of TeamTrack, so a link may point to a TeamTrack file.
> - **Bare arm**: An agent run with the ticket and the repository, and no harness.
> - **Harness arm**: The same run with the harness turned on.
> - **Live evidence**: The files your real A/B run wrote, collected into `live/`.

What is in this folder:

| Path | What it is |
|---|---|
| `work/instructions/` | The map (94 lines), `ARCHITECTURE.md`, `docs/`, and the `add-list-endpoint` skill |
| `work/checker/check_docs.py` | The docs checker, standard library only |
| `work/checker/test_check_docs.py` | The visible tests, unchanged from the starter |
| `work/ab-report.md` | The A/B report, filled from the live evidence |
| `work/live/` | Command output, two experiment exports, score records, run logs |
| `captured/` | Real output of the self-check, the checker, and the grade |

## The approach, step by step

1. **Inventory the original.** The 899-line file has 70 tags: 66 active rules and 4 retired ones
   (`R2.5`, `R3.8`, `R7.5`, `CV-23`). Everything else is background: history, incident notes, review
   comments, questions and answers, a glossary.

2. **Write the checker first, test first.** The visible tests failed against the starter stubs (12 of
   15). The checker was then written until they passed, and it ran after every document of the split.
   A split without a check is a guess. OpenAI's harness team runs "Dedicated linters and CI jobs" on
   its knowledge base for the same reason
   ([Harness engineering](https://openai.com/index/harness-engineering/)).

3. **Give each rule one home.** Each document answers one question an agent asks before it edits code:

   | Tags | Home | Question it answers |
   |---|---|---|
   | `R1.1`-`R1.6`, `R2.1`-`R2.4`, `R2.6`, `CV-22`, `CV-25` | `docs/SECURITY.md` | Who may see or change this data? |
   | `R3.1`-`R3.7`, `R3.9`, `CV-13` to `CV-16` | `docs/design-docs/api-conventions.md` | What shape must the request and response have? |
   | `R4.1`-`R4.7`, `R5.1`-`R5.6`, `R7.1`-`R7.4`, `R7.6`, `CV-11` | `docs/RELIABILITY.md` | Is this write safe to repeat, audited, migrated? |
   | `R6.1`-`R6.5`, `CV-01`, `CV-02`, `CV-19` to `CV-21`, `CV-24` | `ARCHITECTURE.md` | Where does this code go, and what may it import? |
   | `CV-04` to `CV-07`, `CV-17`, `CV-18` | `docs/product-specs/teamtrack-base.md` | How does the product behave? |
   | `CV-03`, `CV-08` to `CV-10` | `docs/QUALITY_SCORE.md` | How do I test it, and what must I not copy? |
   | `CV-12` | `docs/PLANS.md` | How big should this change be? |

   The counts add up to 66 (13 + 12 + 19 + 11 + 6 + 4 + 1). The retired rules appear only as history,
   in `docs/design-docs/decisions.md`.

4. **Write the map.** 94 lines, keyed by what the agent is about to do: a "where to look" table, the
   seven house rules as pointers with anchored links, a "do not copy" warning for the legacy handler,
   the commands, the layout, and a short "before you finish" list. It defines no rule.

5. **Build one skill for the measured task.** Seven of the eight `section-1` tasks are variants of the
   org-wide issue search, a list endpoint, and the A/B reports the tenant isolation and API
   conventions rules (`R1` and `R3`). So the skill is `add-list-endpoint`. Its description says what
   it does and when to use it ("Use when a ticket adds a list, a search, an org-wide view, or a new
   filter on an existing list"). That description is all the agent sees until it opens the skill.

6. **Run the A/B once, live.** The command from the spec, with `--batch a1-reference`, after the tree
   was final. The evidence was collected with `live_evidence.py` and the report filled from
   `ab_summary.py`.

## Design choices and why

- **Rule tags are the unit of coverage.** OpenAI's harness team notes that "A single blob doesn’t lend
  itself to mechanical checks (coverage, freshness, ownership, cross-links)". Tags make coverage
  countable. The overlap floor stops a bare list of ids from passing as coverage.
- **Overlap on content words, threshold 0.5.** It needs no model, gives the same answer every time,
  allows rewording, and catches a rule cut down to its first sentence. The stopword list (common
  words such as "the", which do not count) is fixed in the starter, so every checker computes the
  same numbers.
- **Links resolve through the workspace overlay.** The layer copies the tree onto TeamTrack's root.
  A link from `docs/product-specs/index.md` to `../features/` is correct when it resolves in TeamTrack.
  The checker looks in the tree first, then at the same path in the product.
- **Code-span paths are checked too.** The course's own map points with code spans such as
  `docs/SECURITY.md`. A checker that read only Markdown links would miss most pointers.
- **No new facts.** Every code span in the tree appears in the original or is a real path. That keeps
  the A/B a test of organisation: the bare arm can read every fact in the handbook and the code.
- **Error lines say what to fix.** OpenAI's team writes lint messages "to inject remediation
  instructions into agent context". Each `ERROR` line names the rule or link and where it is.
- **The report is checked against the evidence.** The report's command, runs per arm, `R1` and `R3`
  counts, and links must equal what the score records and exports say. `ab_summary.py` reads only the
  exports, so no number comes from memory.

### Trade-offs and known limits

- The overlap floor is lenient by design. A rule can keep half its words and still lose its point:
  "404" kept, "never 403" dropped. Reviewers still read the documents.
- The code-span path rule skips any span with a space or a colon, so a wrong command in a code span
  is not caught. Checking commands would mean running them.
- The tree check compares file lists, not file contents, because the placement note lists paths only.
  Adding or removing a document after the run is detected; an edit inside one is not.
- If the cost cap stops the A/B early, you keep the shorter batch, because dropping runs is not
  allowed. It then loses part of the "consistent with the command" item.
- Anchors follow GitHub's rule for ASCII headings. Headings with other punctuation may get different
  anchors on other renderers.
- A reference-style link is checked through its definition (`[label]: target`). A `[text][label]`
  with no definition is not reported.

## Alternatives considered

- **Coverage by id only.** Rejected: a file listing 66 ids would pass.
- **Similarity by embeddings (number vectors that stand for a text's meaning) or a model judge.**
  Rejected: it needs keys, costs money, and gives different answers on different runs. The
  self-check must run offline.
- **Verbatim rules.** Rejected: it forbids the rewording that makes focused documents readable.
- **A third arm with the 899-line file injected as `AGENTS.md`.** It would separate "rules in
  context" from "rules organised", but it doubles the A/B cost beyond the $2.50 budget.
- **One skill per house rule.** Rejected: the assignment asks for one skill, and one well-described skill
  is easier to pick than several overlapping ones.
- **Orphan files reported by the checker.** Kept in the self-check instead: reachability is a
  property of the map, while the checker's job is broken pointers and lost rules.

## Common mistakes this avoids

- No rule pasted into the map, so no `rule-in-map` and no second copy to drift.
- No retired rule carried over; history lives in a design doc.
- No link written from the repository root inside `docs/`.
- No TeamTrack file shadowed: nothing in the tree is named `docs/HANDBOOK.md` or sits in
  `docs/features/`.
- No report number typed by hand: every count comes from `ab_summary.py --exports live`.
- The tree was frozen before the A/B, so every harness run log lists exactly the submitted files.

## Run and verify it

From the repository root. These three commands need no keys and no Docker:

```bash
uv run python section-1-instructions/assignment/solution/work/checker/check_docs.py \
  --original section-1-instructions/assignment/starter/original/AGENTS.md \
  --tree section-1-instructions/assignment/solution/work/instructions
uv run python -m pytest -q -p no:cacheprovider section-1-instructions/assignment/solution/work/checker
make check-assignment-1 A1_WORK=section-1-instructions/assignment/solution/work
```

> Your output will differ: your own A/B runs other agent sessions, so its counts, cost, and links will
> not match the reference ones.

The checker and the tests print (real output):

```text
OK: 13 files, 147 links, 66 rules covered
15 passed
```

The full self-check output is in [captured/self-check-solution.txt](captured/self-check-solution.txt),
and the checker output in [captured/checker-solution.txt](captured/checker-solution.txt).

## Evidence

### Live run evidence

The live A/B ran once, on 2026-10-17, with keys and Docker, as in
[SPEC.md, "Run the A/B"](../SPEC.md#run-the-ab), with `--batch a1-reference` and this folder's
`work/instructions/`. It made 48 runs with gpt-6-luna: 24 per arm, 3 for each of the eight Section 1: Instructions
tasks. It cost $0.545310 of the $2.50 budget.

The result is no measurable difference between the arms:

| Measure | Bare arm | Harness arm |
|---|---|---|
| House rule 1: Tenant isolation, runs failing | 0 of 24 | 0 of 24 |
| House rule 3: API conventions, runs failing | 0 of 24 | 0 of 24 |
| Runs aborted (agent time limit) | 2 of 24 | 0 of 24 |

The referee judged every run, the two aborted ones too. With no failing bare run, the map had
nothing to fix on these tasks with this model.

The evidence is in [work/live/](work/live/): the command output, the two experiment exports, the
score records, and the harness run logs. [work/live/README.md](work/live/README.md) explains each
file. The report filled from it is [work/ab-report.md](work/ab-report.md).

The instructor's grade of this folder is 100 out of 100
([captured/grade-solution.txt](captured/grade-solution.txt)), from
`make grade-assignment-1 SUBMISSION=section-1-instructions/assignment/solution/work`, which only the
instructor can run. The self-check passes 24 of 24 checks ([captured/self-check-solution.txt](captured/self-check-solution.txt)). The
grader is not in this repository. Dates, batch, and run ids are on the
[evidence page](../../../docs/evidence/s1.md#s1-a1-solution).

## Sources

- Source 1: Harness engineering: leveraging Codex in an agent-first world, <https://openai.com/index/harness-engineering/>, Ryan Lopopolo (OpenAI), 2026-02-11
