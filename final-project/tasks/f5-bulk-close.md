# Feature 5: Bulk close

The default final feature: one build session, then a test phase. Run it with
`./final-project/run.sh` or `make final FEATURES=bulk-close`.

## What it asks for

At the end of a sprint, a team closes all finished work in a project with one request:
`POST /projects/{project_id}/issues/bulk-close` with a list of 1 to 100 issue ids.

- In-progress issues are closed: their status becomes `done` and their version goes up by one.
- Issues that are already done are skipped with the reason `already_done`.
- Open issues are skipped with the reason `invalid_transition` and stay open.
- If any id is not a live issue of that project in the caller's org, the answer is 404 and nothing
  changes.

## The rules at risk

| House rule | What can go wrong |
|---|---|
| House rule 5: Audit log | Exactly one audit row per request, also when every issue is skipped |
| House rule 1: Tenant isolation | Another org's issue or project must give 404, never 403 |
| House rule 2: Roles | A viewer's bulk close must give 403 |
| "Issues" status rules | Only `in_progress` may move to `done`; open issues must not jump |

The tempting shortcut is to call the single-issue transition in a loop. That writes one audit row
per issue and is not atomic.

## What the referee checks

The referee is the program that scores each arm after the agent stops.

- **Hidden tests:** 46, in three files under
  [platform/teamtrack/tests/hidden/f5/](../../platform/teamtrack/tests/hidden/f5/). 40 test the
  endpoint itself; 3 check that single transitions and issue creation still work; 3 check that the
  bulk close moves each issue's ETag and that search then finds the issues as done.
- **Referee-set mutants:** 3 planted bugs: in-progress issues cannot be closed, closing does not move
  the version, and an archived project accepts the request. The arm's own tests should fail on each.
- **Allowed paths:** the build phase may change `app/api/issues.py`, `app/api/schemas.py`,
  `app/services/issues.py`, `app/repositories/issues.py`, and `tests/visible/**`; the test phase only
  `tests/visible/**`.

## The full spec

- The feature spec the agent reads:
  [platform/teamtrack/docs/features/f5.md](../../platform/teamtrack/docs/features/f5.md).
- The ticket text, session budget, allowed paths, and hidden test files:
  [platform/teamtrack/reference/f5/task.toml](../../platform/teamtrack/reference/f5/task.toml).
- The dataset line `make final FEATURES=bulk-close` runs (feature `F5`, variant `canonical`):
  [platform/datasets/teamtrack-features-v1.jsonl](../../platform/datasets/teamtrack-features-v1.jsonl),
  built from [platform/datasets/sources/tickets.toml](../../platform/datasets/sources/tickets.toml).
- The mutants: [platform/teamtrack/mutants/features/f5.jsonl](../../platform/teamtrack/mutants/features/f5.jsonl).
