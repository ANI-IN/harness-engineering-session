<!-- REPLACE: what your product does, from the user's side: entities, roles, states, and rules a test can check. Rename the file and its row in index.md. -->
# TeamTrack base product

## What TeamTrack is

TeamTrack is a multi-tenant issue tracker: an HTTP API (FastAPI) plus a small web board (Jinja2 and
HTMX). Each customer is an organization ("org"). Orgs have users, projects, project members, issues,
and an audit log. The demo database has two orgs, Acme and Globex. Many customers share one database,
so every row that belongs to a customer carries an `org_id`.

## Users and roles

Roles are `admin`, `member`, and `viewer`. Viewers can read but never write. Creating and updating
users, adding and removing project members, archiving projects, and reading the audit log are
admin-only. Full rules: `docs/SECURITY.md`.

## Projects

Projects are archived, not deleted. Archived projects behave as if they do not exist.

## Issues

| Field | Values |
|---|---|
| `status` | `open`, `in_progress`, `done` |
| `priority` | `low`, `medium`, `high` |
| assignee | optional; a user from the same org |
| `version` | goes up by one on every change |

Allowed status changes:

| From | To |
|---|---|
| open | in_progress |
| in_progress | open or done |
| done | open |

Anything else is 422 `invalid_transition`.

Deleting an issue is a soft delete: it sets `deleted_at`, and deleted issues behave as if they do
not exist (404 on read, hidden from lists).

## Audit log

Every write adds one audit row (House rule 5: Audit log, `docs/RELIABILITY.md`). The audit log is
append-only; there is no endpoint to edit or delete audit rows.

## Web board

The web board lives under `/board` (`app/web/`).
