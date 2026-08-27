# SPEC: exercise-01 scope-auditor

Classifies every change a session made against the scope surface (the
feature list, [../../code/SPEC.md](../../code/SPEC.md)): a change is in
scope only when it targets the active feature. Drift into a queued
feature and drift into a feature the list does not know are both
overreach, each with its own reason. The verdict lives in the exit code
so a session-end gate can consume it.

## CLI surface

```text
main <feature-list.json> <changes.json>
```

The feature list has the library schema's shape (`features[]` with `id`
and `status`, among others); the change log is
`{"changes": [{"step", "file", "feature"}]}`, where `feature` is the id
the session tagged the change with.

## The rule

- **Active features** are the entries whose status is `in-progress`,
  reported in feature-list order.
- A change whose `feature` is active: `in_scope: true`, reason
  `targets the active feature`.
- A change whose `feature` is listed but not active: `in_scope: false`,
  reason `<id> is in the queue, not active`.
- A change whose `feature` is not in the list at all: `in_scope: false`,
  reason `<id> is not in the feature list`.
- `drift.features` lists the drifting feature ids in order of first
  appearance, once each; `drift.count` counts drifting changes.

## Output

```json
{
  "active": ["search-endpoint"],
  "changes": [
    { "step": 1, "file": "src/routes/search.ts", "feature": "search-endpoint", "in_scope": true, "reason": "targets the active feature" }
  ],
  "drift": { "count": 0, "features": [] },
  "clean": true
}
```

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | clean: every change targets the active feature |
| 1 | drift found; the report names every drifting change and why |
| 2 | usage error or unreadable input; stdout empty |

## Fixtures

- `feature_list.json`: four features, `search-endpoint` active, three
  queued (`not-started`).
- `changes/clean-session.json`: four changes, all tagged
  `search-endpoint`; exit 0.
- `changes/mixed-session.json`: six changes; steps 1, 3, and 6 target the
  active feature, step 2 drifts into the queued `delete-endpoint`, step 4
  into `session-metrics` (a feature the session invented; it is not in
  the list), step 5 into the queued `error-shapes`. Drift count 3,
  features `[delete-endpoint, session-metrics, error-shapes]`, exit 1.

## Starter state (the intended failure)

The starter's in-scope test asks whether the change's feature is
*listed* instead of whether it is *active*: the rationalization "it is
on the plan, so it is fine". On `mixed-session.json` it still catches
the invented `session-metrics` (exit 1, matching the expected verdict),
but it declares step 2's drift into the queued `delete-endpoint` in
scope. Verification fails first at
`$.changes[1].in_scope: True != False`, a wrong classification of the
first queued-feature change; the starter must run cleanly and fail only
by producing that wrong classification (and the two queued reasons that
follow from it). `clean-session.json` passes for the starter, because
its trap is precisely the queued feature.

## Expected output

- `clean-session` → `expected/clean-session.json`, exit 0.
- `mixed-session` → `expected/mixed-session.json`, exit 1.
- `missing-file` → stdout empty, exit 2.
