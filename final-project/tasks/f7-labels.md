# Feature 7: Labels

The largest final feature: two build sessions, then a test phase. Run it with
`./final-project/run.sh labels` or `make final FEATURES=labels`.

## What it asks for

Teams tag issues with their own labels, such as "bug", and filter issue lists by label.

- Labels have a name (1 to 50 characters, unique per org ignoring case) and a `#rrggbb` color.
- `GET`, `POST`, `PATCH`, and `DELETE` on `/labels`; deleting a label takes it off every issue.
- Labels go on issues with `POST /issues/{issue_id}/labels` and come off with `DELETE`.
- Every issue response gains `labels`, and the issue lists accept a `label_id` filter.
- Two new tables in exactly one migration, with three seeded labels per org.

## The rules at risk

| House rule | What can go wrong |
|---|---|
| House rule 4: Safe retries | A reused key with a different body must give 409, not a replay |
| House rule 2: Roles | Viewers must get 403 on every label write |
| House rule 5: Audit log | Five audit actions, one row per successful write |
| House rule 1: Tenant isolation | Another org's label id in a body or a filter must give 404 |

House rule 4: a create sent again with the same `Idempotency-Key` header returns the
first result instead of making a duplicate.

Labels touches the most files of the three, including the existing issue endpoints, so the existing
tests that must keep passing are the most at risk here.

## What the referee checks

The referee is the program that scores each arm after the agent stops.

- **Hidden tests:** 64, in four files under
  [platform/teamtrack/tests/hidden/f7/](../../platform/teamtrack/tests/hidden/f7/). 55 test labels
  and their endpoints; 3 check that existing lists, creates, and tenant checks still work; 4 check the
  label filter on Feature 1: Org-wide issue search; 2 check the issue history.
- **Referee-set mutants:** 3 planted bugs: a reused idempotency key with a new body replays, viewers
  can write labels, and label writes add no audit rows.
- **Allowed paths:** the build phase may change the new label files under `app/api/`,
  `app/services/`, and `app/repositories/`, the issue files in the same folders,
  `app/api/schemas.py`, `app/main.py`, `app/db/models.py`, `app/seed.py`, `migrations/versions/**`, and
  `tests/visible/**`.

## The full spec

- The feature spec the agent reads:
  [platform/teamtrack/docs/features/f7.md](../../platform/teamtrack/docs/features/f7.md).
- The ticket text, session budget (25 turns, then 35), allowed paths, and hidden test files:
  [platform/teamtrack/reference/f7/task.toml](../../platform/teamtrack/reference/f7/task.toml).
- The dataset line `make final FEATURES=labels` runs (feature `F7`, variant `canonical`):
  [platform/datasets/teamtrack-features-v1.jsonl](../../platform/datasets/teamtrack-features-v1.jsonl),
  built from [platform/datasets/sources/tickets.toml](../../platform/datasets/sources/tickets.toml).
- The mutants: [platform/teamtrack/mutants/features/f7.jsonl](../../platform/teamtrack/mutants/features/f7.jsonl).
