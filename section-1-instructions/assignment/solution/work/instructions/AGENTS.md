# AGENTS.md

This file is the map of the TeamTrack repository: a table of contents, not the manual. Every rule
lives in exactly one document, and this map says which. Open the document for the part you are
changing before you edit code.

TeamTrack is a multi-tenant issue tracker: an HTTP API (FastAPI) plus a small web board (Jinja2 and
HTMX). Each customer is an org, and every row that belongs to a customer carries an `org_id`.

## Where to look

| When you are about to | Read first |
|---|---|
| add or change a list endpoint | [the add-list-endpoint skill](.agents/skills/add-list-endpoint/SKILL.md) |
| touch a router, service, repository, model, the board, or settings | [ARCHITECTURE.md](ARCHITECTURE.md) (R6) |
| decide who may see or change data | [docs/SECURITY.md](docs/SECURITY.md) (R1, R2) |
| shape a list, an error, a status code, or a request model | [docs/design-docs/api-conventions.md](docs/design-docs/api-conventions.md) (R3) |
| write a create endpoint or any other write | [docs/RELIABILITY.md](docs/RELIABILITY.md) (R4, R5) |
| change the database schema | [docs/RELIABILITY.md](docs/RELIABILITY.md#r7-migrations) (R7) |
| change issue, project, member, or user behaviour | [docs/product-specs/teamtrack-base.md](docs/product-specs/teamtrack-base.md) |
| read a feature spec | [docs/product-specs/index.md](docs/product-specs/index.md) |
| write or run tests | [docs/QUALITY_SCORE.md](docs/QUALITY_SCORE.md) |
| plan a change or check the roadmap | [docs/PLANS.md](docs/PLANS.md) |
| understand why a rule exists | [docs/design-docs/index.md](docs/design-docs/index.md) |

## Rule tags

Every binding rule carries a tag: `R1.1` to `R7.6` for the house rules, `CV-01` and up for team
conventions. Each tag is defined once, in the document the table above names; cite the tag in
reviews instead of pasting the rule. Retired rules are not carried over; their
history is in [docs/design-docs/decisions.md](docs/design-docs/decisions.md).

## House rules at a glance

Every endpoint follows all seven rules, new endpoints included. Automated checks find endpoints in
the OpenAPI schema, so a new endpoint is checked the moment it exists.

- R1 Tenant isolation: another org's resource is 404, never 403. See [docs/SECURITY.md](docs/SECURITY.md#r1-tenant-isolation).
- R2 Roles: viewers get 403 on every write; some writes are admin-only. See [docs/SECURITY.md](docs/SECURITY.md#r2-roles).
- R3 API conventions: list envelope, error envelope, status codes. See [api-conventions.md](docs/design-docs/api-conventions.md).
- R4 Idempotent creates: honour `Idempotency-Key`. See [docs/RELIABILITY.md](docs/RELIABILITY.md#r4-idempotent-creates).
- R5 Audit log: exactly one audit row per write. See [docs/RELIABILITY.md](docs/RELIABILITY.md#r5-audit-log).
- R6 Layering: `app/api` never imports `app.db`. See [ARCHITECTURE.md](ARCHITECTURE.md#r6-layering).
- R7 Migrations: one Alembic head; `alembic upgrade head` works on an empty database. See [docs/RELIABILITY.md](docs/RELIABILITY.md#r7-migrations).

## Do not copy

`GET /v1/issues` (`app/api/legacy_v1.py`) is a legacy endpoint: it is not filtered by org, uses
offset pagination, and returns a bare array. Do not copy it, `repositories.issues.list_all_legacy`,
or `services.legacy`, even when they look like a quicker starting point (CV-03, in
[docs/QUALITY_SCORE.md](docs/QUALITY_SCORE.md#legacy-v1-api)). Copy `GET /projects` and
`POST /projects` in `app/api/projects.py` instead.

`app/api/middleware.py` runs on every request; feature work does not touch it (CV-02).

## Commands

Run these from the TeamTrack folder unless noted.

| Task | Command |
|---|---|
| install dependencies (repository root) | `uv sync` |
| create the database | `alembic upgrade head` |
| start the API | `uvicorn app.main:create_app --factory --reload` |
| run the tests | `python -m pytest tests/visible -q` |
| check the layering (R6) | `lint-imports --config .importlinter` |
| check the migration head (R7) | `alembic heads` |

Demo login: `POST /auth/login` with `{"email": "admin@acme.test"}` returns a token; send it as
`Authorization: Bearer <token>`. The demo token is not secure (CV-22, in
[docs/SECURITY.md](docs/SECURITY.md#demo-authentication)).

## Repository layout

```
app/api/            routers, schemas, dependencies, error handling (calls services)
app/web/            the web board under /board (Jinja2 and HTMX)
app/services/       business logic; every function takes an Actor
app/repositories/   database queries; every customer query takes org_id
app/db/             SQLAlchemy models and engine setup
app/main.py         wires every router into the application
app/seed.py         demo data (orgs Acme and Globex, stable ids)
migrations/         Alembic environment and migrations/versions/
tests/visible/      the tests you run and extend
```

## Before you finish

- The house rules hold for every endpoint you added or changed.
- Tests in `tests/visible/` cover the happy path and each rule (CV-09, in
  [docs/QUALITY_SCORE.md](docs/QUALITY_SCORE.md#testing)).
- `python -m pytest tests/visible -q` passes and existing tests keep passing, unchanged (CV-10).
- `lint-imports --config .importlinter` keeps both contracts; `alembic heads` shows one head.
- Nothing copied from the legacy /v1 code; no change to `app/api/middleware.py`.
