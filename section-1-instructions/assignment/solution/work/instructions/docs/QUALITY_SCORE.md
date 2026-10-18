# Quality score

Grades for each product domain and architectural layer, the gaps we track, and how tests keep the
grades honest. Update a row when a change closes or opens a gap.

Grades: **meets rules** (no gap recorded), **gap** (a known shortfall on the roadmap), **do not
copy** (breaks house rules; kept only until removal).

## Product domains

| Domain | Grade | Notes |
|---|---|---|
| Projects | meets rules | `POST /projects` is the pattern for idempotent creates (R4.5) |
| Users | meets rules | creating and updating users is admin-only (R2.2) |
| Project members | meets rules | adding and removing members is admin-only (R2.2) |
| Issues | gap | issue creation does not accept `Idempotency-Key` yet (R4.6) |
| Audit log | meets rules | append-only (R5.5); reading it is admin-only |
| Legacy /v1 API | do not copy | see below |

## Architectural layers

| Layer | Grade | Notes |
|---|---|---|
| `app/api/` | meets rules | never imports `app.db` (R6.1); `app/api/middleware.py` is shared (CV-02) |
| `app/web/` | meets rules | never imports `app.db` (R6.2) |
| `app/services/` | meets rules, except `services.legacy` | every function takes an `Actor` (CV-01) |
| `app/repositories/` | meets rules, except `repositories.issues.list_all_legacy` | every customer query takes `org_id` (R1.1) |
| `app/db/` | meets rules | schema changes go through Alembic (R7.1) |

## Legacy /v1 API

`GET /v1/issues` is a legacy endpoint kept for one old reporting client. It predates tenant
isolation. The handler is `app/api/legacy_v1.py`; the OpenAPI schema marks it deprecated.

- [CV-03] Do not copy `GET /v1/issues`, `repositories.issues.list_all_legacy`, or `services.legacy`:
  they are not filtered by org, use offset pagination, and return a bare array. They are scheduled
  for removal. New endpoints must follow the house rules, even when the legacy code looks like a
  quicker starting point.

Its R1 leak is part of the check baseline and its R3 envelope failure is exempt, so neither counts
against your change, unless your change makes them worse or copies them into a new endpoint.

## Testing

- [CV-08] Tests live in `tests/visible/`. Use the fixtures in `tests/visible/conftest.py`: `client`
  gives a fresh seeded app, `auth(user_id)` gives headers for a user, and `acme` and `globex` hold
  the seeded IDs.
- [CV-09] For any endpoint you add, test both the happy path and the house rules: another org's IDs
  give 404, viewers get 403 on writes, lists use the envelope, and writes add one audit row.
- [CV-10] Do not change existing tests to make a change pass.

`client` builds the app with a temporary SQLite file, with `TEAMTRACK_CREATE_SCHEMA` and seeding on,
so every test starts from the same data. `auth(acme.viewer)` returns
`{"Authorization": "Bearer tt-3"}`. `error_code(response)` checks that a body is exactly the error
envelope and returns its code. Run one file while you work
(`python -m pytest tests/visible/test_issues.py -q`), then `python -m pytest tests/visible -q`.

| File | Covers |
|---|---|
| `tests/visible/test_auth.py` | login, tokens, `GET /me` |
| `tests/visible/test_tenant_isolation.py` | R1 probes with Globex IDs |
| `tests/visible/test_roles.py` | R2: viewers and admin-only writes |
| `tests/visible/test_lists.py` | R3 list envelope and cursors |
| `tests/visible/test_idempotency_and_audit.py` | R4 and R5 |
| `tests/visible/test_issues.py` | issue behaviour, transitions, soft delete |
| `tests/visible/test_projects_users_members.py` | projects, users, members |
| `tests/visible/test_legacy_and_schema.py` | the legacy endpoint and the OpenAPI schema |
| `tests/visible/test_board.py` | the board |

Test patterns for a new list endpoint: `.agents/skills/add-list-endpoint/references/tests.md`.

Automated checks for R1 to R7 discover endpoints from the OpenAPI schema, so a new endpoint is checked
the moment it exists. Each rule's check is the last clause of the rule (R1.6, R2.6, R3.9, R4.7, R5.6,
R6.5, R7.6).
