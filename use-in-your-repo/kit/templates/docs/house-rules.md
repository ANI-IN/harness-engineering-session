<!-- REPLACE: this page explains how TeamTrack's seven house rules map onto your API. Fill the "Rules this repository keeps" table, delete the rows you drop, and keep the rest as the reference for the next person who changes a rule. -->
# House rules and their checks

A house rule is a team convention written down as one checkable sentence, with a check that finds
every violation. TeamTrack has seven, House rules 1 to 7 (check ids `R1` to `R7`). `shipharness check` runs them against any FastAPI app,
in process, with no model calls. It finds endpoints in the app's OpenAPI schema, so an endpoint added
tomorrow is checked the day it exists. Everything specific to your app goes through one file,
`harness/shipharness_adapter.py`.

## Rules this repository keeps

<!-- REPLACE: one row per rule you keep, with the document that states it. TeamTrack keeps all seven. -->
| Rule | Kept | Stated in |
|---|---|---|
| House rule 1: Tenant isolation | yes | `docs/SECURITY.md` |
| House rule 2: Roles | yes | `docs/SECURITY.md` |
| House rule 3: API conventions | yes | `docs/design-docs/api-conventions.md` |
| House rule 4: Safe retries | yes | `docs/RELIABILITY.md` |
| House rule 5: Audit log | yes | `docs/RELIABILITY.md` |
| House rule 6: Layering | yes | `ARCHITECTURE.md` |
| House rule 7: Migrations | yes | `docs/RELIABILITY.md` |

## What each check does and what it needs from your app

| Rule | What the check does | Adapter methods it calls | TeamTrack value | Drop it when |
|---|---|---|---|---|
| House rule 1 (`R1`) | As the home tenant, points every endpoint at the other tenant's ids: another tenant's id in a path must give 404, a 2xx body must not hold the other tenant's data, and a call without credentials must not succeed | `create_app()`, `orgs()`, `ids()`, `headers()`, `is_foreign()` | orgs `acme` and `globex`; another org's issue is 404 | one tenant owns all data |
| House rule 2 (`R2`) | Calls every POST, PUT, PATCH, and DELETE as a viewer; each must give 403 | `create_app()`, `orgs()`, `ids()`, `headers()` | role `viewer` | every caller may write |
| House rule 3 (`R3`) | Schemathesis requests for every operation with a fixed seed, plus envelope assertions: errors are `{"error": {"code", "message"}}`, lists are `{"items", "next_cursor"}`, no `offset` or `page` parameter | `create_app()`, `orgs()`, `ids()`, `headers()` | the envelopes in `docs/design-docs/api-conventions.md` | your API uses other envelopes (write your own check) |
| House rule 4 (`R4`) | Sends every create twice with the same `Idempotency-Key` and counts rows per table in the SQLite file; a second row is a duplicate | `create_app()`, `orgs()`, `ids()`, `headers()`, `bookkeeping_tables` | `POST /projects` is the pattern | clients never retry creates, or the app does not use SQLite |
| House rule 5 (`R5`) | Counts audit rows before and after each write: one per successful write, none for a refused one | `create_app()`, `orgs()`, `ids()`, `headers()`, `audit_count()` | table `audit_log` | you keep no audit log |
| House rule 6 (`R6`) | Runs import-linter with the contract from the adapter, never the repository's own config | `layering_contract()` | `app.api` and `app.web` never import `app.db` | never; write the contract for your packages |
| House rule 7 (`R7`) | `alembic heads` must show one head and `alembic upgrade head` must work on an empty database | `migration_env()` | `TEAMTRACK_DATABASE_URL` | you have no database migrations |

Every rule also calls `exemptions()`: findings listed there are reported as info and do not count.
`body_overrides()` gives request bodies that generated data cannot get right. The board check in
shipharness is specific to TeamTrack's web board and is not covered here.

The check that existing tests keep passing is not a house rule, but it runs the same way:
`--rules regression` with `regression_targets` in `harness/check-params.json`.

## Run the checks

<!-- REPLACE: the path of your shipharness checkout (TeamTrack's README clones it to ~/shipharness) and the rules you keep. -->
From your repository root, record today's violations once, then check against that baseline:

```bash
PYTHONPATH=harness uv run --project ~/shipharness shipharness check --app . \
  --adapter shipharness_adapter:HouseRulesAdapter --rules R1,R2,R3,R4,R5,R6,R7 \
  --json > harness/check-baseline.json
PYTHONPATH=harness uv run --project ~/shipharness shipharness check --app . \
  --adapter shipharness_adapter:HouseRulesAdapter --rules R1,R2,R3,R4,R5,R6,R7 \
  --baseline harness/check-baseline.json
```

Each check prints one line, `PASS` or `FAIL`, with `new=` violations, `baseline=` violations, and the
number of probes. Exit codes: 0 no new violation, 3 a new violation, 1 an error. CI runs the second
command on every push (`.github/workflows/shipharness.yml`).

## How to check that a rule works

Break the rule on purpose and run its check: it must fail. For House rule 6 (`R6`) in TeamTrack, add
`from app.db import models` to a file in `app/api/`, run `--rules R6`, and read the `FAIL` line with
the import chain; then undo the change. A check that never fails proves nothing.

## When it fails

| Output | Cause | Fix |
|---|---|---|
| `FAIL  r1_tenant ... new=1` with an endpoint and a status | A new endpoint breaks the rule | Fix the endpoint; the line names it |
| `error: app directory not found: <dir>` | `--app` points at the wrong folder | Pass the folder that holds your app package |
| `ModuleNotFoundError: No module named 'shipharness_adapter'` | `PYTHONPATH` does not include `harness` | Run from the repository root with `PYTHONPATH=harness` |
| `check crashed: ...` and exit 1 | The adapter or the app raised an error | Read the error; usually `create_app()` cannot import the app |
| `check crashed: AttributeError: 'HouseRulesAdapter' object has no attribute 'create_app'` | `--rules` names a rule whose adapter methods you deleted | Drop the rule from `--rules`, or add the methods the table above lists for it |
| `baseline=` grows and `new=0` | A known violation got worse but was already listed | Fix it, then record the baseline again |

## Adding your own rule

Use the house-rules skill (`.claude/skills/house-rules/` or `.agents/skills/house-rules/`): it writes
the rule document, a check stub, and a test with a seeded violation, and asks for an error message
that says how to fix the problem.
