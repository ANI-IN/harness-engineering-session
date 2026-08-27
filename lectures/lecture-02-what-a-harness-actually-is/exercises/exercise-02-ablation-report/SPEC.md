# SPEC: exercise-02 ablation-report

Aggregates six minimal-harness-loop reports into one controlled-variable
ablation comparison. The fixture reports under `fixtures/reports/` are the
lecture demo's own committed outputs (`full.json` plus the five
`disable-<subsystem>.json` files), copied verbatim; their figures originate
from the demo's fixtures, not from prose.

## CLI surface

```text
main <reports-dir>
```

`<reports-dir>` must contain `full.json` (the baseline) and
`disable-<name>.json` for each of instructions, state, environment, tools,
feedback.

## Comparison rules

Per ablation, in the fixed order instructions, state, environment, tools,
feedback:

- `outcome_changed`: the ablated run's `outcome` differs from the
  baseline's.
- `issues`: the number of issue strings in the ablated report.
- `signature`: the ablated report's first issue string, or `null` when it
  has none.

`all_degraded` is true when every ablation changed the outcome. For the
committed fixtures it is true: removing any one subsystem degrades the run.

## Output

```json
{
  "baseline": { "outcome": "completed-verified", "issues": 0 },
  "ablations": [
    { "disabled": "instructions", "outcome": "...", "outcome_changed": true, "issues": 1, "signature": "..." }
  ],
  "all_degraded": true
}
```

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | report emitted |
| 2 | usage error or `<reports-dir>` is not a directory; stdout empty |

## Starter state (the intended failure)

The starter aggregates counts correctly but reports `outcome_changed` false
and `signature` null everywhere, so `all_degraded` comes out false.
Verification fails with a report mismatch first diverging at
`$.ablations[0].outcome_changed: False != True`. The starter must run
cleanly and fail only by producing that wrong report.

## Expected output

- `basic` case: `fixtures/reports` → `expected/ablation-report.json` (kind
  json; the grading authority for both tracks).
