# SPEC: exercise-01 claim-audit

The lecture demo's gate ([../../code/SPEC.md](../../code/SPEC.md)) derives
the claim by replaying its own scripted session. This exercise audits a
**recorded** claim: a JSON file a session left behind, listing every check
with the status it claims, the basis for it, and the evidence text it
recorded at the time. The audit re-executes the claim against the
workspace as it is now.

## CLI surface

```text
main <workspace-dir> <claim-file>
```

`<workspace-dir>` carries `checks.json` and the probed files, with the
demo's check kinds, detail strings, and line-ending rule unchanged.
`<claim-file>` is:

```json
{
  "done": true,
  "checks": [ { "id", "status": "pass" | "fail", "basis": "executed" | "predicted", "evidence": "..." } ]
}
```

`evidence` is what the session wrote down when it established the status:
the engine's detail string for an executed check, a sentence of reasoning
for a predicted one. It is input to the audit and never a substitute for
re-execution.

## The audit

Every claimed check is re-executed through the engine, in the claim's
order, regardless of its recorded basis. Output:

```json
{
  "workspace": "...",
  "claim": { "done", "green", "executed", "predicted" },
  "reexecution": [ { "id", "layer", "claimed", "basis", "actual", "detail", "verdict" } ],
  "verdict": { "divergences", "result": "earned" | "premature" }
}
```

`green` counts claimed passes; `executed` and `predicted` count bases.
`detail` is always the engine's fresh detail string. A row is `confirmed`
when `actual` equals `claimed` and `diverged` otherwise; `result` is
`earned` when no row diverged.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `earned`: every claimed status reproduced |
| 1 | `premature`: at least one claimed status did not reproduce |
| 2 | usage error, missing workspace or claim file, or a claim with `done: false` (nothing to audit); stdout empty |

## Fixtures

- `workspaces/workspace-drifted`: the workspace moved after the session
  recorded its evidence. `tests/unit-export.txt` now reads `result=fail`
  (a later edit broke the header row), and `logs/e2e-export.log` never
  appeared; the other three checks hold.
- `workspaces/workspace-earned`: all five checks pass.
- `claims/claim-recorded-green.json` (the trap): four checks recorded as
  executed with the exact detail strings the engine printed when they
  were true, one predicted. Against `workspace-drifted` the recorded unit
  pass is stale.
- `claims/claim-predictions.json`: the same claim with the unit check
  predicted instead of executed, so the stale pass carries no recorded
  evidence to trust.
- `claims/claim-earned.json`: the recorded-green claim over
  `workspace-earned`, where every recorded status still holds.

## Starter state (the intended failure)

The starter re-executes predicted checks but accepts executed ones on
their record: for a row whose basis is `executed`, it copies the claimed
status into `actual` and the recorded evidence into `detail`. The audit
therefore cannot see that a recorded pass has gone stale.

Verification fails first on the `stale-evidence` case at
`$.reexecution[1].actual: 'pass' != 'fail'`: the unit check was green
when the session recorded it and is red now, and the starter reports the
record, not the workspace. The other two cases pass under the starter,
because trusting a record only misleads when the record and the
workspace disagree, which is exactly what the trap fixture arranges. The
starter must run cleanly and fail only by producing that wrong value.

## Expected output

- `stale-evidence`: `workspace-drifted` + `claim-recorded-green.json` →
  `expected/stale-evidence.json`, exit 1 (two divergences: the stale unit
  pass and the predicted end-to-end run).
- `predictions-caught`: `workspace-drifted` + `claim-predictions.json` →
  `expected/predictions-caught.json`, exit 1.
- `earned-confirmed`: `workspace-earned` + `claim-earned.json` →
  `expected/earned-confirmed.json`, exit 0.
