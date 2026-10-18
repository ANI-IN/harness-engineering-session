# House rules and their checks

A house rule is a team convention written down as one checkable sentence, with a check that finds
every violation. This repository is a library: no HTTP API, no tenants, no database. So it keeps
one of TeamTrack's seven rules, adapted, plus the check that existing tests keep passing.

## Rules this repository keeps

| Rule | Kept | Why | Stated in |
|---|---|---|---|
| R1 Tenant isolation | no | no tenants and no HTTP API | |
| R2 Roles | no | no callers with roles | |
| R3 API conventions | no | no HTTP API | |
| R4 Idempotent creates | no | no create endpoints | |
| R5 Audit log | no | no writes to record | |
| R6 Layering | yes, as BQ1 | module dependencies must point one way so modules stay copyable | `ARCHITECTURE.md` |
| R7 Migrations | no | no database | |
| Existing tests keep passing | yes | the suite and the doctests are the specification | `docs/QUALITY_SCORE.md` |

BQ2 (guarded imports) is checked in review until it has a check of its own (`docs/PLANS.md`).

## What the adapter holds

`harness/shipharness_adapter.py` keeps two methods: `layering_contract()` returns the BQ1
import-linter contract, and `exemptions()` returns none. shipharness calls `exemptions()` on every
run, R6 calls `layering_contract()`, and the regression check calls neither, so the methods only
R1-R5 and R7 need are deleted. Asking for one of those rules anyway (`--rules R2`) ends with
`check crashed: AttributeError: 'HouseRulesAdapter' object has no attribute 'create_app'`.
`harness/check-params.json` sets `regression_targets` to `--doctest-modules boltons tests`: the
regression check passes them to pytest, so the doctests count as existing tests.

## Run the checks

```bash
PYTHONPATH=harness uv run --project ~/shipharness shipharness check --app . \
  --adapter shipharness_adapter:HouseRulesAdapter --rules R6,regression \
  --params harness/check-params.json --json > harness/check-baseline.json
PYTHONPATH=harness uv run --project ~/shipharness shipharness check --app . \
  --adapter shipharness_adapter:HouseRulesAdapter --rules R6,regression \
  --params harness/check-params.json --baseline harness/check-baseline.json
```

Exit codes: 0 no new violation, 3 a new violation, 1 an error. CI runs the second command on every
push (`.github/workflows/shipharness.yml`).

## How to check that a rule works

Add `from .queueutils import PriorityQueue` to `boltons/typeutils.py`, run the second command, and
read the `FAIL` line for `r6_layering` with the import chain. Then undo the change.
