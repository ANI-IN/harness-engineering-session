# SPEC: exercise-02 knowledge-gap-report

Computes the knowledge visibility gap from an inventory of project
decisions: what fraction of what the team knows is somewhere the agent can
actually see.

## CLI surface

```text
main <inventory.jsonl>
```

The inventory is JSONL, one entry per line (blank lines ignored; LF and
CRLF both accepted): `{"id", "decision", "location", "critical"}`.

## The visibility rule

A decision is **in-repo** exactly when its `location` starts with the
prefix `repo:` (the rest being a repository path). A location that merely
mentions repositories, such as `Confluence: repo guidelines page` or
`Slack #repo-help thread`, is outside: the agent cannot see it, whatever
it is named.

## Output

```json
{
  "total": 10,
  "in_repo": 6,
  "outside": 4,
  "visibility_gap": 0.4,
  "critical_outside": ["k-versioning", "k-rate-limits"],
  "verdict": "needs-externalization"
}
```

- `visibility_gap` = outside / total (IEEE 754 division; 4/10 must
  serialize as `0.4`, 1/10 as `0.1`; an empty inventory yields the
  number 0).
- `critical_outside` lists the ids of outside entries with
  `critical: true`, in input order.
- `verdict` is `acceptable` when the gap is at most 0.1 (the lecture's
  keep-the-gap-under-10% heuristic), else `needs-externalization`.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | report emitted |
| 1 | malformed inventory (non-JSON line or missing field); stdout empty |
| 2 | usage error or unreadable file; stdout empty |

## Fixtures

- `inventory.jsonl`: 10 entries, 6 in-repo, 4 outside (2 critical),
  including the two traps whose locations mention "repo" without being in
  one.
- `inventory-clean.jsonl`: 10 entries, 1 outside and non-critical: gap 0.1,
  verdict `acceptable`.

## Starter state (the intended failure)

The starter's `in_repo` is a naive first draft: any location containing
the substring "repo" (case-insensitive) counts as in-repo. The two trap
entries make it overcount: it reports 8 in-repo, gap 0.2, and drops
`k-versioning` (a critical decision) from `critical_outside`. Verification
fails with a report mismatch first diverging at
`$.critical_outside[0]: 'k-rate-limits' != 'k-versioning'`: the divergence
names the critical decision that silently vanished from the outside list.
The starter must run cleanly and fail only by producing these wrong values.

## Expected output

- `scattered` case: `fixtures/inventory.jsonl` → `expected/gap-report.json`.
- `clean` case: `fixtures/inventory-clean.jsonl` →
  `expected/gap-report-clean.json` (also pins the 0.1 boundary being
  acceptable).
