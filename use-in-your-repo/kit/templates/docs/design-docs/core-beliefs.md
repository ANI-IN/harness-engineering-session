<!-- REPLACE: the principles behind your house rules, each with the rule and the check that enforce it. -->
# Core beliefs

The principles behind TeamTrack's house rules. Each one names the rule that carries it and the check
that enforces it.

| Belief | Rule | Check |
|---|---|---|
| No org may see or change another org's data, and the API must not reveal that another org's resource exists. | House rule 1: Tenant isolation (`docs/SECURITY.md`) | an Acme user with Globex IDs gets 404 on every endpoint and method |
| Viewers can read but never write; a few writes are admin-only. | House rule 2: Roles (`docs/SECURITY.md`) | every write endpoint called as a viewer returns 403 |
| Every endpoint looks the same to a client: one list envelope, one error envelope, fixed status codes. | House rule 3: API conventions (`docs/design-docs/api-conventions.md`) | Schemathesis plus envelope assertions |
| Retrying a create is safe. | House rule 4: Safe retries (`docs/RELIABILITY.md`) | a duplicate POST with the same key leaves exactly one new record |
| Every write leaves exactly one audit row, and the audit log is append-only. | House rule 5: Audit log (`docs/RELIABILITY.md`) | audit rows counted before and after each write |
| Routers get data only through services. | House rule 6: Layering (`ARCHITECTURE.md`) | the import-linter contract |
| The schema always migrates from an empty database to one head. | House rule 7: Migrations (`docs/RELIABILITY.md`) | `alembic heads` shows one head; a fresh `alembic upgrade head` succeeds |

Working habits that follow from these beliefs:

- New endpoints follow the house rules even when legacy code looks like a quicker starting point
  (`docs/QUALITY_SCORE.md`).
- Keep queries portable: SQLite is used for development and the demo.
- Prefer small pull requests that touch only the files a feature needs.
