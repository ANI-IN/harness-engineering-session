# SPEC: exercise-02 rebuild-cost

Compares the session-simulator's two committed runs and states what the
continuity artifacts buy, with every saving oriented the same way.

## CLI surface

```text
main <reports-dir>
```

`<reports-dir>` contains `with-handoff.json` and `no-handoff.json`: the
lecture demo's committed outputs, copied verbatim (their figures originate
from the demo's fixtures, not from prose).

## The orientation rule

`savings` reports, per metric, how much better the with-handoff run did,
so **positive always means the handoff won**:

- cost metrics (`reacquisition_lines`, `rework_sessions`, `drift_events`):
  without-handoff minus with-handoff;
- the completion metric (`features_completed`): with-handoff minus
  without-handoff.

## Output

```json
{
  "with_handoff": { "reacquisition_lines": 0, "features_completed": 0, "rework_sessions": 0, "drift_events": 0 },
  "without_handoff": { "...": 0 },
  "savings": { "...": 0 }
}
```

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | report emitted |
| 2 | usage error or `<reports-dir>` is not a directory; stdout empty |

## Starter state (the intended failure)

The starter's `savings` subtracts in one fixed direction for every metric,
flipping the sign of each saving and making the handoff look like a cost.
Verification fails with a report mismatch first diverging at
`$.savings.drift_events: -2 != 2`. The starter must run cleanly and fail
only by producing these wrong values.

## Expected output

- `basic` case: `fixtures/reports` → `expected/rebuild-cost.json` (kind
  json; the grading authority for both tracks).
