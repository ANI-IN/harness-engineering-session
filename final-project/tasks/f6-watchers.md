# Feature 6: Watchers

A final feature over two build sessions, then a test phase. Run it with
`./final-project/run.sh watchers` or `make final FEATURES=watchers`.

## What it asks for

Users follow the issues they care about and see them in one list.

- Any writer can start or stop watching an issue: `PUT` and `DELETE /issues/{issue_id}/watchers/me`.
  Watching twice changes nothing and writes no audit row.
- Anyone in the org can list an issue's watchers, and see their own list with `GET /me/watching`.
- Admins can add or remove any user of their own org as a watcher.
- Watchers live in a new table, added with exactly one migration, with a few seeded watchers.

## The rules at risk

| House rule | What can go wrong |
|---|---|
| House rule 1: Tenant isolation | An admin adds another org's user as a watcher |
| House rule 2: Roles | A member manages other people's watching; a viewer writes |
| House rule 5: Audit log | One row per real change; none for a no-op or a refused write |
| House rule 7: Migrations | Exactly one new migration on the current head (the latest migration) |

The session stop matters here: the first session ends after 20 turns, partway through the feature.
The second session starts with an empty context and must pick up the work from the repository.

## What the referee checks

The referee is the program that scores each arm after the agent stops.

- **Hidden tests:** 54, in three files under
  [platform/teamtrack/tests/hidden/f6/](../../platform/teamtrack/tests/hidden/f6/). 49 test the
  watcher endpoints; 3 check that existing reads and deletes still work; 2 check the issue history
  and the version shown in the watching list.
- **Referee-set mutants:** 3 planted bugs: the user lookup drops the org filter, members count as
  admins, and deleted issues still answer the watcher endpoints.
- **Allowed paths:** the build phase may change the new watcher files under `app/api/`,
  `app/services/`, and `app/repositories/`, plus `app/api/schemas.py`, `app/main.py`,
  `app/db/models.py`, `app/seed.py`, `migrations/versions/**`, and `tests/visible/**`.

## The full spec

- The feature spec the agent reads:
  [platform/teamtrack/docs/features/f6.md](../../platform/teamtrack/docs/features/f6.md).
- The ticket text, session budget (20 turns, then 30), allowed paths, and hidden test files:
  [platform/teamtrack/reference/f6/task.toml](../../platform/teamtrack/reference/f6/task.toml).
- The dataset line `make final FEATURES=watchers` runs (feature `F6`, variant `canonical`):
  [platform/datasets/teamtrack-features-v1.jsonl](../../platform/datasets/teamtrack-features-v1.jsonl),
  built from [platform/datasets/sources/tickets.toml](../../platform/datasets/sources/tickets.toml).
- The mutants: [platform/teamtrack/mutants/features/f6.jsonl](../../platform/teamtrack/mutants/features/f6.jsonl).
