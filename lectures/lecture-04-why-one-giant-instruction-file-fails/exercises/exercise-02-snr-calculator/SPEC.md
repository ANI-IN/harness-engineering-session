# SPEC: exercise-02 snr-calculator

Computes per-task instruction signal-to-noise for a single instruction
file: how much of what the agent loads is actually for the task at hand.

## CLI surface

```text
main <tree-dir> <tasks.json>
```

The tree's `AGENTS.md` uses the demo's instruction format
(`- [<topic>] <text>`); `<tasks.json>` is `{"tasks": [{"id", "topics"}]}`.

## The relevance rule

A line is **relevant** to a task exactly when it is an instruction line
whose topic tag names one of the task's topics. Prose that mentions a
topic word ("do not copy old api examples") is context cost, not signal:
it still gets loaded, and it still is not an instruction the task can act
on.

- `loaded_lines` = the entry file's line count (this exercise loads only
  the entry).
- `relevant_lines` = tag-matched instruction lines.
- `snr` = `relevant_lines / loaded_lines`; `mean_snr` accumulates the
  per-task SNRs left to right with plain addition (see the demo SPEC's
  summation rule) and divides by the task count.

## Output

```json
{
  "tasks": [
    { "id": "...", "loaded_lines": 0, "relevant_lines": 0, "snr": 0 }
  ],
  "mean_snr": 0
}
```

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | report emitted |
| 2 | usage error, no `AGENTS.md`, or unreadable tasks file; stdout empty |

## Fixtures

`fixtures/tree/AGENTS.md` is the demo's 45-line monolith, whose prose
mentions "api" and "db" outside instruction lines; `fixtures/tasks.json`
holds three tasks.

## Starter state (the intended failure)

The starter's `relevant_count` is a naive first draft: it counts any line
containing a topic word as relevant, so prose about the api inflates the
api signal (the first task counts 10 relevant lines where the tag rule
finds 6). Verification fails with a report mismatch first diverging at
`$.mean_snr: 0.1259259259259259 != 0.08148148148148149`: the inflated
average, visible before the per-task rows because report keys compare in
sorted order. The starter must run cleanly and fail only by producing
these wrong values.

## Expected output

- `basic` case: `fixtures/tree` + `fixtures/tasks.json` →
  `expected/snr-report.json` (kind json; the grading authority for both
  tracks).
