<!-- [walkthrough:S1:agents_md] start -->
# AGENTS.md

This file is the map of the TeamTrack repository: a table of contents, not the manual. It tells you
where each rule lives. Open the document for the part you are changing before you edit code.

TeamTrack is a multi-tenant issue tracker: an HTTP API (FastAPI) plus a small web board (Jinja2 and
HTMX). Each customer is an org, and every customer row carries an `org_id`.

## Where to look

| When you are about to | Read first |
|---|---|
| add or change an endpoint | `.agents/skills/add-endpoint/SKILL.md` (step by step) |
| touch a router, service, repository, or model | `ARCHITECTURE.md` (layers, House rule 6: Layering) |
| decide who may see or change data | `docs/SECURITY.md` (House rule 1: Tenant isolation, House rule 2: Roles) |
| shape a list, an error, or a status code | `docs/design-docs/api-conventions.md` (House rule 3: API conventions) |
| write a create endpoint or any write | `docs/RELIABILITY.md` (House rule 4: Safe retries, House rule 5: Audit log) |
| change the database schema | `docs/RELIABILITY.md` (House rule 7: Migrations) |
| change issue or project behaviour | `docs/product-specs/teamtrack-base.md` |
| write or run tests | `docs/QUALITY_SCORE.md` (testing, known gaps) |
| plan a change or check the roadmap | `docs/PLANS.md` |
| understand why the code is shaped this way | `docs/design-docs/index.md` |
| look up a tool (Alembic, import-linter) | `docs/references/` |

## House rules at a glance

Every endpoint follows all seven rules, new endpoints included. Automated checks find endpoints in
the OpenAPI schema, so a new endpoint is checked the moment it exists.

- House rule 1: Tenant isolation. Another org's resource is 404, never 403. See `docs/SECURITY.md`.
- House rule 2: Roles. Viewers get 403 on every write; some writes are admin-only. See `docs/SECURITY.md`.
- House rule 3: API conventions. List envelope, error envelope, status codes. See `docs/design-docs/api-conventions.md`.
- House rule 4: Safe retries. Creates honour `Idempotency-Key`. See `docs/RELIABILITY.md`.
- House rule 5: Audit log. One audit row per write. See `docs/RELIABILITY.md`.
- House rule 6: Layering. `app/api` never imports `app/db`. See `ARCHITECTURE.md`.
- House rule 7: Migrations. One Alembic head; upgrade works on an empty database. See `docs/RELIABILITY.md`.
<!-- [walkthrough:S1:agents_md] end -->

## Do not copy

`GET /v1/issues` (`app/api/legacy_v1.py`) is a legacy endpoint kept for one old reporting client. It
is not filtered by org, uses offset pagination, and returns a bare array; it is scheduled for removal.
Do not copy it, even when it looks like a quicker starting point. The same applies to
`repositories.issues.list_all_legacy` and `services.legacy`. For a create endpoint, `POST /projects`
shows the pattern. Details: `docs/QUALITY_SCORE.md`.

`app/api/middleware.py` runs on every request. Feature work does not touch it.

## Commands

Run these from the TeamTrack folder unless noted.

| Task | Command |
|---|---|
| install dependencies (repository root) | `uv sync` |
| create the database | `alembic upgrade head` |
| start the API | `uvicorn app.main:create_app --factory --reload` |
| run the tests | `python -m pytest tests/visible -q` |
| check the layering (House rule 6) | `lint-imports --config .importlinter` |
| check the migration head (House rule 7) | `alembic heads` |

Demo login: `POST /auth/login` with `{"email": "admin@acme.test"}` returns a token; send it as
`Authorization: Bearer <token>`. Users exist for each role in each org (`admin@`, `member@`,
`viewer@` at `acme.test` and `globex.test`). The demo token is not secure and is for local use only.

## Repository layout

```
app/api/            routers, schemas, dependencies, error handling (calls services)
app/web/            the web board under /board (Jinja2 and HTMX)
app/services/       business logic; every function takes an Actor
app/repositories/   database queries; every customer query takes org_id
app/db/             SQLAlchemy models and engine setup
app/main.py         wires everything together
app/seed.py         demo data (orgs Acme and Globex)
migrations/         Alembic environment and migrations/versions/
tests/visible/      the tests you run and extend
docs/               the system of record (this map points into it)
```

## How the docs are organised

`docs/` is the system of record. This map stays short on purpose; the facts live in the files it
points to. `docs/HANDBOOK.md` holds the same rules as one long handbook; when you need a rule, the
focused document above is quicker to read.

## Before you finish

- The house rules above hold for every endpoint you added or changed.
- Tests in `tests/visible/` cover the happy path and the rules: another org's IDs give 404, viewers
  get 403 on writes, lists use the envelope, writes add one audit row.
- `python -m pytest tests/visible -q` passes and existing tests keep passing, unchanged.
- `lint-imports --config .importlinter` and `alembic heads` (one head) pass.
