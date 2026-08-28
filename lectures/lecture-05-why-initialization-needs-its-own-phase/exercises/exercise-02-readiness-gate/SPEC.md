# SPEC: exercise-02 readiness-gate

Turns readiness check results into a tiered verdict: blockers stop a
session from starting; advice does not, but must stay visible. The tier
lives in the exit code, which is what makes it usable from `init.sh` and
CI alike.

## CLI surface

```text
main <check-results.json>
```

The input is `{"checks": [{"id", "severity", "passed"}]}` with severity
`blocker` or `advice`.

## The tiering rule

- Any failed blocker: verdict `blocked`, exit 1.
- No failed blockers but failed advice: verdict `ready-with-advice`,
  exit 3 (distinct from 1 so callers can proceed while surfacing it, and
  distinct from 2, the usage-error code).
- Nothing failed: verdict `ready`, exit 0.

## Output

```json
{ "blockers_failed": ["..."], "advice_failed": ["..."], "verdict": "ready" }
```

Failed ids appear in input order. Exit code 2 remains usage error or
unreadable input (stdout empty).

## Fixtures

`all-pass.json` (exit 0), `blocked.json` (one failed blocker plus one
failed advice, exit 1), `advice-only.json` (two failed advice checks,
exit 3, the case that separates the tiers).

## Starter state (the intended failure)

The starter counts correctly but treats every failure as a blocker,
erasing the tier. On `advice-only.json` it prints verdict `blocked` and
exits 1 where the SPEC requires `ready-with-advice` and exit 3.
Verification fails with `exit code 1 != expected 3`: a wrong verdict
delivered through the exit code, before stdout is even compared. The
starter must run cleanly and fail only with that wrong verdict.

## Expected output

- `all-pass` → `expected/all-pass.json`, exit 0.
- `blocked` → `expected/blocked.json`, exit 1.
- `advice-only` → `expected/advice-only.json`, exit 3.
