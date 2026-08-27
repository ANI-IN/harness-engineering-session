# SPEC: exercise-01 fresh-session-answers

Same contract as the lecture demo
([../../code/SPEC.md](../../code/SPEC.md)): answer the five fresh-session
questions from repository contents alone, extracting each answer from its
specific language-neutral artifact. This exercise applies it to fresh
fixture repositories, and the starter ships three naive extractors.

## CLI surface

```text
main <repo-dir>
```

Question ids, extraction rules, report shape, `visibility_gap`, and exit
codes are identical to the demo SPEC.

## Fixtures

- `repos/repo-atlas`: fully mapped (5/5, gap 0, exit 0), and built to trap
  each naive extractor: its `AGENTS.md` carries the prose line "Always
  verify your work before claiming done." *before* the real
  `- Verification:` line, and its `claude-progress.md` opens with a
  heading.
- `repos/repo-thin`: instructions and a Run line only (2/5, gap 0.6,
  exit 1).

## Starter state (the intended failure)

The starter is a genuine partial implementation: all five extractors run,
but three are naive first drafts, each with one realistic mistake the
atlas fixture exposes:

| Naive extractor | Its mistake | What it returns on repo-atlas |
| --- | --- | --- |
| how-organized | answers from the instructions file's overview line instead of `docs/ARCHITECTURE.md` | the atlas-tool overview, source `AGENTS.md` |
| how-to-verify | takes the first line *mentioning* verification instead of the `- Verification:` line | the prose "Always verify your work before claiming done." |
| where-are-we | takes the progress file's first line (its heading) instead of the `- Next best step:` line | `# Progress` |

Verification fails with a report mismatch first diverging at
`$.questions[1].answer` (the how-organized answer is the overview line, not
the architecture doc's first prose line). The starter must run cleanly and
fail only by producing these wrong values; a crash or all-null answers is a
bug in the starter, not the intended state.

## Expected output

- `atlas` case: `fixtures/repos/repo-atlas` → `expected/atlas.json` (kind
  json), exit 0.
- `thin` case: `fixtures/repos/repo-thin` → `expected/thin.json` (kind
  json), exit 1: the blanks are reported, and the non-zero exit is the
  fresh-session verdict.
