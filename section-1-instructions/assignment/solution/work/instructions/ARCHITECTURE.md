# Architecture

A top-level map of TeamTrack's packages and how they are layered. House rule R6 lives here, with
the conventions about wiring, the board, configuration, and shared middleware.

## Layers

The code is layered. A layer may only call the layer below it.

| Package | Holds |
|---|---|
| `app/web/` | the web board under `/board` (Jinja2 and HTMX) |
| `app/api/` | routers, request and response schemas, dependencies, error handling |
| `app/services/` | business logic |
| `app/repositories/` | database queries |
| `app/db/` | SQLAlchemy models and engine setup |

`app/main.py` wires everything together. `app/seed.py` creates the demo data.

## R6 Layering

- [R6.1] The api package never imports `app.db`: `app/api` gets data only through services.
- [R6.2] `app/web` never imports `app.db` either. The board may use the dependencies in
  `app/api/deps.py` and calls services, the same way routers do.
- [R6.3] A layer only calls the layer below it: web, then api, then services, then repositories,
  then db. Never call upwards.
- [R6.4] If you need data in a router, add or extend a service function; do not import models or
  sessions into `app/api/`.
- [R6.5] The R6 check is the import-linter contract: `lint-imports --config .importlinter` must keep
  both contracts.

The two contracts in `.importlinter`: "R6: app.api and app.web never import app.db" (a forbidden
contract) and "Layers: web -> api -> services -> repositories -> db" (a layers contract).

## Services and wiring

- [CV-01] Every service function takes an `Actor` (the authenticated user, with `user_id`, `org_id`,
  and `role`) and works only inside `actor.org_id`.
- [CV-19] A new router module must be included in `app/main.py`, which wires every router into the
  application; a router that is not included does not exist.

Where things live:

| File | What is in it |
|---|---|
| `app/api/deps.py` | `get_db`, `current_actor`, `require_writer`, `require_admin`, the `Id` type |
| `app/api/pagination.py` | `Page`, `page_params`, `decode_cursor`, `encode_cursor`, `to_page` |
| `app/api/errors.py` | the error envelope handlers |
| `app/api/schemas.py` | request and response models |
| `app/services/context.py` | `Actor` |
| `app/services/errors.py` | `NotFound`, `Forbidden`, `Conflict`, `Invalid`, `BadRequest`, `Unauthorized` |
| `app/services/audit.py` | `record()` |
| `app/services/idempotency.py` | `run_once()` |
| `app/repositories/common.py` | `page()`, `split_page()` |
| `app/db/models.py` | tables |
| `app/db/session.py` | engine and session factory |

One request, `GET /projects/{project_id}`: the middleware assigns the request id; FastAPI validates
the path id against the `Id` type; `current_actor` builds the `Actor` from the bearer token (no token
is 401); the router calls `projects.get(db, actor, project_id)`; the service calls the repository
with `actor.org_id`; no row (missing, archived, or another org's) means `NotFound`, which becomes
404 `not_found`; a row is converted with `ProjectOut.model_validate` and returned with 200.

## Tables

Every tenant-owned row carries `org_id` (`app/db/models.py`).

| Table | Columns worth knowing | Notes |
|---|---|---|
| `orgs` | `id`, `name`, `slug` | `slug` is unique (`acme`, `globex`) |
| `users` | `id`, `org_id`, `email`, `name`, `role` | `email` is unique across orgs |
| `projects` | `id`, `org_id`, `name`, `key`, `archived_at` | unique (`org_id`, `key`) |
| `project_members` | `project_id`, `user_id`, `added_at` | no `org_id`: reach it through the project |
| `issues` | `id`, `org_id`, `project_id`, `title`, `status`, `priority`, `assignee_id`, `version`, `deleted_at` | soft delete |
| `audit_log` | `id`, `org_id`, `actor_id`, `action`, `entity`, `entity_id`, `at` | append-only |
| `idempotency_keys` | `org_id`, `key`, `endpoint`, `request_hash`, `status_code`, `response_json` | unique (`org_id`, `key`, `endpoint`) |

`project_members` rows are reached through a project, and the project lookup is scoped to the org:
never query `project_members` without first loading the project through the service. Timestamps are
timezone-aware UTC (`utcnow` in `app/db/base.py`).

## The web board

The board lives in `app/web/` under `/board`: a login page to pick a demo user, the project list, one
board per project with a column per status, and an issue page with an edit form. Templates are in
`app/web/templates/`, static files (including the vendored HTMX file) in `app/web/static/`. It keeps
the selected user's demo token in the `tt_session` cookie and calls the same services as the API, so
the tenant and role rules apply to it too (`docs/SECURITY.md`, R2.4).

- [CV-20] Board cards carry `data-org` and `data-issue-id` attributes. Keep them when you change the
  templates: `tests/visible/test_board.py` finds cards by these attributes.

## Configuration and logging

- [CV-21] Configuration comes from environment variables prefixed `TEAMTRACK_`, read by
  `TeamTrackSettings` in `app/settings.py`; a new setting is a new field on that class.
- [CV-24] Every response carries an `X-Request-ID` header; a client may send its own and the same
  value comes back, so logs and client reports can be matched.

Settings in use: `TEAMTRACK_DATABASE_URL` (default `sqlite:///./teamtrack.db`; Alembic reads it too,
see `migrations/env.py`), `TEAMTRACK_CREATE_SCHEMA` (tests only), `TEAMTRACK_SEED`,
`TEAMTRACK_LOG_JSON`, and `TEAMTRACK_LOG_REQUESTS`. The access log is written with structlog under
the logger name `teamtrack.http`.

## Shared middleware

- [CV-02] `app/api/middleware.py` holds shared middleware that runs on every request. It is shared
  infrastructure: changes to it affect every endpoint and need a separate review. Feature work does
  not touch it.

Today it sets the `X-Request-ID` header and writes the access log line.
