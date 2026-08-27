# SPEC: exercise-01 router-validator

Validates a router-style instruction tree: the shape lecture 04 argues for
only works if it is *kept* that shape, so the rules become executable
checks.

## CLI surface

```text
main <tree-dir>
```

A tree is an `AGENTS.md` entry file plus optional `docs/*.md` topic files.
Instruction lines and hard constraints use the demo's format
(`- [<topic>] <text>`, `!` marks hard). A route line matches
`- docs/<name>.md` at the start of an entry-file line.

## The four checks (fixed order)

| id | Passes when |
| --- | --- |
| `entry-length` | the entry file is at most 20 lines |
| `routes-resolve` | every route line's target file exists in the tree |
| `hard-in-entry` | no hard constraint appears outside the entry file (the entry is where hard constraints belong: top of the file the agent always loads) |
| `no-duplicates` | no rule **text** (the part after the topic tag) appears more than once across the tree; the same text under a different tag is still a duplicate |

Violations carry `{file, line, detail}`; files are scanned entry first,
then docs in name order, lines in order.

## Output

```json
{
  "checks": [
    { "id": "entry-length", "passed": true, "violations": [] }
  ],
  "ok": true
}
```

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | report emitted (the verdict is the `ok` field) |
| 2 | usage error or no `AGENTS.md` in the tree; stdout empty |

## Fixtures

- `trees/tree-good`: a clean router (all four checks pass).
- `trees/tree-broken`: three seeded violations, one per naive mistake: a
  route to `docs/deploy.md` which does not exist, an `[audit!]` hard
  constraint inside `docs/db.md`, and the pagination rule's text duplicated
  under a different topic tag.

## Starter state (the intended failure)

The starter is a genuine partial implementation: all four checks run
(`entry-length` correctly), but three are naive first drafts:

| Naive check | Its mistake | What the fixtures expose |
| --- | --- | --- |
| `routes-resolve` | trusts that the route line parses instead of testing the target file | misses the dead `docs/deploy.md` route |
| `hard-in-entry` | scans only the entry file, where hard constraints are allowed | flags the legitimate entry constraint on `tree-good` and misses the real `docs/db.md` violation |
| `no-duplicates` | compares whole lines, so a different topic tag hides a duplicate | misses the duplicated pagination text |

Verification fails first on `tree-good` with
`diverges at $.checks[2].passed: False != True`: the naive hard-constraint
check reports a violation in the one place hard constraints belong. The
starter must run cleanly and fail only by producing these wrong values.

## Expected output

- `tree-good` case → `expected/tree-good.json` (kind json).
- `tree-broken` case → `expected/tree-broken.json` (kind json).
