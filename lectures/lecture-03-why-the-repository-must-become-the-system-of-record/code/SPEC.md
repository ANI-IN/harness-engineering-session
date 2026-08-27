# SPEC: fresh-session-reader

The fresh-session test, mechanized: can a brand-new agent session answer
the five basic questions from repository contents alone? Every answer is
extracted from a specific language-neutral artifact; both tracks read the
same bytes and must emit the same report. `expected/` is the grading
authority.

## CLI surface

```text
main <repo-dir>
```

## The five questions and their extraction rules

| id | Question | Answer extracted from | Rule |
| --- | --- | --- | --- |
| `what-is-this` | What is this system? | `AGENTS.md` or `CLAUDE.md` (that order) | first non-empty line that is not a heading |
| `how-organized` | How is it organized? | `docs/ARCHITECTURE.md` | first non-empty line that is not a heading |
| `how-to-run` | How do I run it? | the instructions file | the `- Run: <command>` line's value |
| `how-to-verify` | How do I verify it? | the instructions file | the `- Verification: <command>` line's value |
| `where-are-we` | Where are we now? | `claude-progress.md` | the `- Next best step: <text>` line's value |

A question with no extractable answer reports `answered: false` with
`answer` and `source` both null. Sources are reported exactly as the
strings in `expected/` (filename, plus the line name where a specific line
is the rule).

## Output

```json
{
  "questions": [
    { "id": "...", "question": "...", "answered": true, "answer": "...", "source": "..." }
  ],
  "answered": 0,
  "total": 5,
  "visibility_gap": 0,
  "ready": false
}
```

`visibility_gap` is unanswered over total (IEEE 754 division; 3/5 must
serialize as `0.6`; a fully mapped repo yields the number 0).

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | all five questions answered: a fresh session can start without guessing |
| 1 | at least one question unanswered; the report on stdout names the blanks |
| 2 | usage error or `<repo-dir>` is not a directory; stdout empty |

## Fixtures

- `repos/repo-mapped`: answers all five (gap 0, exit 0).
- `repos/repo-blank-spots`: answers only `what-is-this` and `how-to-run`
  (the seeded blanks: no architecture doc, no Verification line, no
  progress file; gap 0.6, exit 1, caught by the report's `answered: false`
  entries in both tracks identically).

## Language-neutrality (this lecture's obligation)

Everything the reader consults is markdown: the same files that the course
library ships as templates. Neither implementation needs to know what
language the audited project is written in, and the two implementations
extract identical answers from identical bytes, enforced by conformance.
