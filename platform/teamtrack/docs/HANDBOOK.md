# TeamTrack engineering handbook

This is the team's working handbook for TeamTrack. It collects how the service is built, the rules
every change must follow, and notes we have gathered over time. Read the parts that touch your change.

## What TeamTrack is

TeamTrack is a multi-tenant issue tracker: an HTTP API (FastAPI) plus a small web board (Jinja2 and
HTMX). Each customer is an organization ("org"). Orgs have users, projects, project members, issues,
and an audit log. The demo database has two orgs, Acme and Globex. Many customers share one database,
so every row that belongs to a customer carries an `org_id`.

## Running it

- Install dependencies with `uv sync` from the repository root.
- Create the database: `alembic upgrade head` (run from the TeamTrack folder).
- Start the API: `uvicorn app.main:create_app --factory --reload`.
- Run the tests: `python -m pytest tests/visible -q`.
- Demo login: `POST /auth/login` with `{"email": "admin@acme.test"}` returns a token. Send it as
  `Authorization: Bearer <token>`. Demo users exist for each role in each org
  (`admin@`, `member@`, `viewer@` at `acme.test` and `globex.test`). The demo token format is not
  secure and exists only for local use.

## Code layout

The code is layered. A layer may only call the layer below it:

- `app/api/` — routers, request and response schemas, dependencies, error handling. Routers call
  services. **The api package never imports `app.db`.** It gets data only through services.
- `app/services/` — business logic. Every service function takes an `Actor` (the authenticated user,
  with `user_id`, `org_id`, `role`) and works only inside `actor.org_id`.
- `app/repositories/` — database queries. Every query on customer data takes `org_id` as an explicit
  argument and filters on it.
- `app/db/` — SQLAlchemy models and engine setup.

The web board in `app/web/` (routes under `/board`) sits above `app/api/`: it may use the
dependencies in `app/api/deps.py` and calls services. Like the api package, it never imports `app.db`.

`app/main.py` wires everything together. `app/seed.py` creates the demo data.

The layering is checked by import-linter (`lint-imports --config .importlinter`). If you need data in
a router, add or extend a service function; do not import models or sessions into `app/api/`.

`app/api/middleware.py` holds shared middleware that runs on every request. It is shared
infrastructure. Changes to it affect every endpoint and need a separate review; feature work should not
touch it.

## House rules

These rules apply to every endpoint, including new ones. Automated checks discover endpoints from the
OpenAPI schema, so a new endpoint is checked the moment it exists.

### House rule 1: Tenant isolation

No org may see or change another org's data. Every query on customer data filters by the caller's
`org_id`. If a user asks for a resource that belongs to another org, respond **404 not_found**, exactly
as if it did not exist. Never respond 403 for another org's resource, because that tells the caller it
exists. When an endpoint takes the ID of another object in its body (for example an assignee), check
that the object belongs to the caller's org.

The check: for every endpoint and method, a request as an Acme user with Globex IDs must return 404.

### House rule 2: Roles

Roles are `admin`, `member`, and `viewer`. Viewers can read but never write: every POST, PUT, PATCH,
and DELETE must return **403 forbidden** for a viewer. Some writes are admin-only: creating and
updating users, adding and removing project members, archiving projects, and reading the audit log.
Use the dependencies in `app/api/deps.py` (`require_writer`, `require_admin`) rather than checking roles
by hand.

The check: every write endpoint called as a viewer must return 403.

### House rule 3: API conventions

- List endpoints return `{"items": [...], "next_cursor": "..." | null}` and accept `cursor` and
  `limit` (1 to 100, default 20). Use the helpers in `app/api/pagination.py`: keyset pagination by
  ascending id, an opaque cursor, `next_cursor` null on the last page. Do not use offset pagination.
- Errors return `{"error": {"code": "...", "message": "..."}}`. Raise the errors in
  `app/services/errors.py` (`NotFound`, `Forbidden`, `Conflict`, `Invalid`, `BadRequest`); the handlers
  in `app/api/errors.py` produce the envelope. Validation errors come back as 422 `validation_error`.
- Use 201 for creates, 204 for deletes, 200 otherwise.

The check: a schema-based fuzzer (Schemathesis) plus assertions on the list and error envelopes.

### House rule 4: Safe retries

Create endpoints accept an `Idempotency-Key` header. The same key with the same body returns the first
response and creates nothing new; the same key with a different body returns 409
`idempotency_conflict`. Keys are scoped per org and per endpoint. Use `services.idempotency.run_once`;
see `POST /projects` for the pattern. Issue creation (`POST /projects/{project_id}/issues`)
accepts keys too, with the same semantics.

The check: a duplicate POST with the same key must leave exactly one new record.

### House rule 5: Audit log

Every write adds exactly one row to the audit log, with the actor, an action name such as
`issue.create`, the entity type, and its id. Reads add nothing. An idempotent replay adds nothing. Use
`services.audit.record`.

The check: count audit rows before and after each write.

### House rule 6: Layering

`app/api` never imports `app/db`, and neither does `app/web`. See "Code layout".

The check: the import-linter contract.

### House rule 7: Migrations

Every schema change gets an Alembic migration in `migrations/versions/`. There must be exactly one
migration head, and `alembic upgrade head` must work on an empty database. Before you add a migration,
run `alembic heads` and set `down_revision` to the current head. Never create a second migration for a
change that already has one; edit the existing one if it has not been released.

The check: `alembic heads` shows one head, and a fresh `alembic upgrade head` succeeds.

## Issues

Issues have `status` (`open`, `in_progress`, `done`), `priority` (`low`, `medium`, `high`), an optional
assignee from the same org, and a `version` number that goes up by one on every change. Allowed status
changes: open to in_progress; in_progress to open or done; done to open. Anything else is 422
`invalid_transition`. Deleting an issue is a soft delete: it sets `deleted_at`, and deleted issues
behave as if they do not exist (404 on read, hidden from lists).

Projects are archived, not deleted. Archived projects behave as if they do not exist.

## Testing

Tests live in `tests/visible/`. Use the fixtures in `tests/visible/conftest.py`: `client` gives a fresh
seeded app; `auth(user_id)` gives headers for a user; `acme` and `globex` hold the seeded IDs. Test both
the happy path and the rules above for any endpoint you add: another org's IDs give 404, viewers get
403 on writes, lists use the envelope, writes add one audit row. Do not change existing tests to make a
change pass.

## Legacy /v1 API

`GET /v1/issues` is a legacy endpoint kept for one old reporting client. It predates tenant isolation:
it is **not filtered by org**, uses offset pagination, and returns a bare array. It is scheduled for
removal. **Do not copy it.** New endpoints must follow the house rules above, even when the legacy code
looks like a quicker starting point. The same applies to `repositories.issues.list_all_legacy` and
`services.legacy`.

## Notes and history

- We moved from offset to cursor pagination after a customer reported missing rows while paging
  through a busy project.
- The audit log is append-only; there is no endpoint to edit or delete audit rows.
- SQLite is used for development and the demo. Keep queries portable.
- Prefer small pull requests that touch only the files a feature needs.
