# AGENTS.md: TeamTrack (read all of this before you change anything)

This file is everything the TeamTrack team knows about building and changing the service, in one
place. It started as a one-page note for new engineers in 2024 and grew every time something went
wrong. Coding agents read it at the start of every task, and so do people. If you are an agent:
read the whole file before you edit code, and follow every tagged rule.

Sections, in the order they were added:

1. How to read this file
2. What TeamTrack is
3. Running TeamTrack
4. Code layout and layering
5. House rules (R1 to R7)
6. Issues, projects, members, and users
7. Tables
8. Endpoint inventory
9. Seed data
10. Validation and request handling
11. Testing
12. The web board
13. Configuration and logging
14. The legacy /v1 API
15. Shared middleware
16. Working practices and review checklist
17. Team notes and history
18. Questions we keep getting
19. Glossary
20. Roadmap

---

## 1. How to read this file

In March 2025 we started tagging every binding rule with an ID, so that reviews and incident notes
can cite the rule instead of pasting it. The tags look like this:

- `R1.1` to `R7.6` are house rules. The number before the dot is the house rule (R1 Tenant
  isolation, R2 Roles, R3 API conventions, R4 Idempotent creates, R5 Audit log, R6 Layering, R7
  Migrations); the number after the dot is the clause.
- `CV-01` and up are team conventions: binding, but not checked by an automated house-rule check.
- A tag followed by "(retired ...)" is a rule we no longer follow. We keep retired rules in the
  file so that old review comments still make sense. Do not apply them.

Untagged text is background: history, explanations, examples, and answers to questions. When
untagged text and a tagged rule disagree, the tagged rule wins, and please tell the team so we can
fix the text.

Each rule is tagged once, where it was first written down. Some rules are repeated later in plain
words (in the questions section, for example); the repetition carries no tag.

A note on length: we know this file is long. Several people have asked for it to be split up. The
last attempt stalled because nobody wanted to own the split. Until someone does, this is the file.

---

## 2. What TeamTrack is

TeamTrack is a multi-tenant issue tracker: an HTTP API (FastAPI) plus a small web board (Jinja2 and
HTMX). Each customer is an organization ("org"). Orgs have users, projects, project members, issues,
and an audit log.

Many customers share one database, so every row that belongs to a customer carries an `org_id`.
That single fact explains most of the rules below: if a query forgets the `org_id` filter, one
customer sees another customer's data, and that is the worst bug this service can have.

The demo database has two orgs, Acme and Globex. Acme is org 1 and Globex is org 2; the IDs are
fixed so that cross-tenant tests always mean the same thing (see section 9).

Stack, for orientation:

- FastAPI for the HTTP API, with pydantic request and response models.
- SQLAlchemy 2.1 for the database layer; SQLite in development and in the demo.
- Alembic for schema migrations.
- pydantic-settings for configuration (environment variables prefixed `TEAMTRACK_`).
- structlog for logging.
- Jinja2 templates and HTMX for the board; the HTMX file is vendored in `app/web/static/`.
- pytest for tests; import-linter for the layering contract.

The service is small on purpose. There is no background worker, no cache, and no message queue. If
a change seems to need one, talk to the team first.

---

## 3. Running TeamTrack

All commands run from the TeamTrack folder unless a line says otherwise.

- Install dependencies with `uv sync` from the repository root.
- Create the database: `alembic upgrade head`.
- Start the API: `uvicorn app.main:create_app --factory --reload`.
- Run the tests: `python -m pytest tests/visible -q`.
- Check the layering: `lint-imports --config .importlinter`.
- Check the migration head: `alembic heads`.

The application is built by the factory in `app/main.py`; uvicorn calls `create_app` because of
`--factory`. The database URL comes from `TEAMTRACK_DATABASE_URL` and defaults to
`sqlite:///./teamtrack.db`. Alembic reads the same setting (see `migrations/env.py`), so
`alembic upgrade head` and the API always talk to the same file.

To load the demo data into an empty database, set `TEAMTRACK_SEED=true` before you start the API.
Seeding does nothing when the database already has orgs.

Demo login: `POST /auth/login` with `{"email": "admin@acme.test"}` returns a token. Send it as
`Authorization: Bearer <token>`. Demo users exist for each role in each org (`admin@`, `member@`,
`viewer@` at `acme.test` and `globex.test`).

- [CV-22] The demo token is `tt-<user id>` and is not secure: it exists only for local use and
  demos. Never build anything that trusts it outside a laptop.

A quick smoke test after starting the API:

1. `GET /health` answers `{"status": "ok"}`; it needs no token.
2. Log in as `admin@acme.test` and call `GET /me`; you get the Acme admin.
3. Call `GET /projects`; you get Acme's two projects in the list envelope.
4. Open `/board` in a browser and pick a demo user on the login page.

If `alembic upgrade head` fails with "table already exists", the database was probably created by
the test setting `TEAMTRACK_CREATE_SCHEMA`; delete the file and run the upgrade again.

First day on the team, in order:

1. Run the service and the smoke test above.
2. Read section 5 (house rules) completely, then section 11 (testing).
3. Read `app/api/projects.py` from top to bottom: it shows a list, an idempotent create, a read, an
   update, and an archive, each with the right role dependency.
4. Read `tests/visible/test_tenant_isolation.py`: it shows how an R1 test looks.
5. Pick a small ticket and follow "Adding an endpoint, step by step" in section 16.

---

## 4. Code layout and layering

The code is layered. A layer may only call the layer below it.

- `app/api/`: routers, request and response schemas, dependencies, error handling. Routers call
  services.
- `app/services/`: business logic.
- `app/repositories/`: database queries.
- `app/db/`: SQLAlchemy models and engine setup.

The web board in `app/web/` (routes under `/board`) sits above `app/api/`.

`app/main.py` wires everything together. `app/seed.py` creates the demo data.

- [R6.1] The api package never imports `app.db`: `app/api` gets data only through services.
- [R6.2] `app/web` never imports `app.db` either. The board may use the dependencies in
  `app/api/deps.py` and calls services, the same way routers do.
- [R6.3] A layer only calls the layer below it: web, then api, then services, then repositories,
  then db. Never call upwards.
- [R6.4] If you need data in a router, add or extend a service function; do not import models or
  sessions into `app/api/`.
- [R6.5] The R6 check is the import-linter contract: `lint-imports --config .importlinter` must
  keep both contracts.
- [CV-01] Every service function takes an `Actor` (the authenticated user, with `user_id`,
  `org_id`, and `role`) and works only inside `actor.org_id`.

The two import-linter contracts in `.importlinter` are named "R6: app.api and app.web never import
app.db" (a forbidden contract) and "Layers: web -> api -> services -> repositories -> db" (a layers
contract). The first one is the house rule; the second one keeps the order of the layers.

Where things live, one level deeper:

```
app/api/deps.py          get_db, current_actor, require_writer, require_admin, the Id type
app/api/pagination.py    Page, page_params, decode_cursor, encode_cursor, to_page
app/api/errors.py        the error envelope handlers
app/api/schemas.py       request (*In, *Create, *Patch) and response (*Out) models
app/api/middleware.py    request id and access log (shared; see section 15)
app/services/context.py  Actor
app/services/errors.py   NotFound, Forbidden, Conflict, Invalid, BadRequest, Unauthorized
app/services/audit.py    record()
app/services/idempotency.py  run_once()
app/repositories/common.py   page(), split_page()
app/db/models.py         tables
app/db/session.py        engine and session factory
```

Why the layers: in 2024 a router imported a model "just for one query" and forgot the `org_id`
filter. The fix took ten minutes; finding the leak took a week. Since then the layers are checked by
a tool, not by reviewers.

One request from start to finish, `GET /projects/{project_id}` as an example:

1. The middleware assigns the request id (section 15).
2. FastAPI validates the path id against the `Id` type.
3. `current_actor` reads the bearer token and builds the `Actor`; no token is 401.
4. The router calls `projects.get(db, actor, project_id)` in the service layer.
5. The service calls the repository with `actor.org_id`; the repository filters on it.
6. No row (missing, archived, or another org's) means `NotFound`, which the handler turns into
   404 `not_found` in the error envelope.
7. A row is converted with `ProjectOut.model_validate` and returned with 200.

---

## 5. House rules (R1 to R7)

These rules apply to every endpoint, including new ones. Automated checks discover endpoints from
the OpenAPI schema, so a new endpoint is checked the moment it exists. Each rule ends with a clause
that says how its check works, so you can predict what the check will do to your change.

R6 Layering is in section 4, next to the layout it protects.

### R1 Tenant isolation

No org may see or change another org's data.

- [R1.1] Every query on customer data filters by the caller's `org_id`. Repositories take `org_id`
  as an explicit argument and filter on it; a repository function never guesses the org.
- [R1.2] If a user asks for a resource that belongs to another org, respond 404 `not_found`,
  exactly as if it did not exist.
- [R1.3] Never respond 403 for another org's resource, because a 403 tells the caller that the
  resource exists.
- [R1.4] When an endpoint takes the ID of another object in its body (for example an assignee, or a
  user to add as a project member), check that the object belongs to the caller's org before you
  use it.
- [R1.5] Lists only ever contain rows of the caller's org, including lists that span several
  projects.
- [R1.6] The R1 check: for every endpoint and method, a request as an Acme user with Globex IDs must
  return 404.

How the code does it today: services call `projects.get(session, actor, project_id)` or
`issues.get(...)`, which raise `NotFound` when the row is missing or belongs to another org. The
service functions never take an `org_id` from the request; they read `actor.org_id`.

A body ID from another org is not a missing path resource, so it gets its own answer:

- [CV-25] An ID in a request body that does not belong to the caller's org is answered 422, with
  code `invalid_assignee` for issue assignees and `invalid_user` for project members.

The R1 check counts a violation whenever an Acme request with a Globex ID gets anything other than
404. A 2xx whose body contains Globex data is also counted as a leak. Both show up as new
violations against the baseline; the legacy `/v1/issues` leak is part of the baseline.

### R2 Roles

- [R2.1] Roles are `admin`, `member`, and `viewer`. Viewers can read but never write: every POST,
  PUT, PATCH, and DELETE must return 403 forbidden for a viewer.
- [R2.2] Some writes are admin-only: creating and updating users, adding and removing project
  members, and archiving projects. Reading the audit log is admin-only as well.
- [R2.3] Use the dependencies in `app/api/deps.py` (`current_actor`, `require_writer`,
  `require_admin`) rather than checking roles by hand.
- [R2.4] The board follows the same rule: a viewer who tries to create, edit, or move an issue on
  the board gets 403.
- [R2.5] (retired 2024-11, superseded by R2.2) Members may archive projects they belong to.
- [R2.6] The R2 check: every write endpoint called as a viewer must return 403.

`current_actor` authenticates the bearer token and returns the `Actor`; `require_writer` lets
`admin` and `member` through; `require_admin` lets only `admin` through. A missing or invalid token
is 401 `unauthorized` before any role check runs.

R1 comes before R2: an Acme viewer who asks to change a Globex issue gets 404, not 403, because the
issue does not exist for them.

### R3 API conventions

- [R3.1] List endpoints return `{"items": [...], "next_cursor": "..." | null}`.
- [R3.2] Lists accept `cursor` and `limit` (1 to 100, default 20) and use keyset pagination by
  ascending id with an opaque cursor; `next_cursor` is null on the last page. Use the helpers in
  `app/api/pagination.py` and `app/repositories/common.py`.
- [R3.3] Do not use offset pagination.
- [R3.4] Errors return `{"error": {"code": "...", "message": "..."}}`. Raise the errors in
  `app/services/errors.py` (`NotFound`, `Forbidden`, `Conflict`, `Invalid`, `BadRequest`); the
  handlers in `app/api/errors.py` produce the envelope.
- [R3.5] Validation errors come back as 422 `validation_error`.
- [R3.6] Use 201 for creates, 204 for deletes, and 200 otherwise.
- [R3.7] A cursor that cannot be decoded is 400 with code `invalid_cursor`.
- [R3.8] (retired 2025-03, superseded by R3.3) Admin exports may page with `offset` and `limit`.
- [R3.9] The R3 check: a schema-based fuzzer (Schemathesis) plus assertions on the list and error
  envelopes.

How a list endpoint fits together, using `GET /projects` as the example (`list_projects` in
`app/api/projects.py`):

1. The router takes `params: PageParams = Depends(page_params)`, which reads `cursor` and `limit`.
2. It calls the service with `decode_cursor(params.cursor)` and `params.limit`.
3. The repository builds the query with `page(...)` (rows after the cursor id, ordered by id,
   `limit + 1` rows) and cuts it with `split_page(...)`, which also returns the next cursor id.
4. The router returns `to_page(rows, next_after, ProjectOut.model_validate)`, which encodes the
   cursor and builds the `Page` response model.

Error codes you will see, and where they come from:

| Status | Code | Raised by |
|---|---|---|
| 400 | `bad_request` | `BadRequest` |
| 400 | `invalid_cursor` | `decode_cursor` |
| 401 | `unauthorized` | `Unauthorized` (missing or invalid token, unknown email at login) |
| 403 | `forbidden` | `Forbidden` (role checks) |
| 404 | `not_found` | `NotFound` (missing, deleted, archived, or another org's resource) |
| 405 | `method_not_allowed` | the framework, wrapped in the envelope |
| 409 | `conflict` | `Conflict` (project key or email already used, member already added) |
| 409 | `idempotency_conflict` | `run_once` (see R4) |
| 422 | `validation_error` | request validation and `Invalid` |
| 422 | `invalid_transition` | issue status changes (section 6) |
| 422 | `invalid_assignee` | an assignee from another org |
| 422 | `invalid_user` | a project member from another org |
| 500 | `internal_error` | any unexpected exception |

Status codes are part of the contract. A create that returns 200 or a delete that returns a body
fails the R3 check.

### R4 Idempotent creates

- [R4.1] Create endpoints accept an `Idempotency-Key` header.
- [R4.2] The same key with the same body returns the first response and creates nothing new.
- [R4.3] The same key with a different body returns 409 `idempotency_conflict`.
- [R4.4] Keys are scoped per org and per endpoint.
- [R4.5] Use `services.idempotency.run_once`; see `POST /projects` for the pattern. The service
  function takes `commit: bool = True` and the router passes `commit=False`, so `run_once` commits
  once.
- [R4.6] Issue creation does not support keys yet; that is on the roadmap.
- [R4.7] The R4 check: a duplicate POST with the same key must leave exactly one new record.

How the pattern in `app/api/projects.py` fits together: the router reads the `Idempotency-Key`
header, defines a `create()` function that calls the service with `commit=False` and returns the
response body, and passes both to `idempotency.run_once` with the endpoint name (`"POST /projects"`)
and the request body. `run_once` stores the response under the org, the key, and the endpoint, then
commits. `POST /users` follows the same pattern.

Adding a project member is a create too, but a second identical request is answered 409 `conflict`
("already a member"), so it never makes a second record.

### R5 Audit log

- [R5.1] Every write adds exactly one row to the audit log, with the actor, an action name such as
  `issue.create`, the entity type, and its id.
- [R5.2] Reads add nothing.
- [R5.3] An idempotent replay adds nothing.
- [R5.4] Use `services.audit.record`.
- [R5.5] The audit log is append-only; there is no endpoint to edit or delete audit rows.
- [R5.6] The R5 check: count audit rows before and after each write.

Action names in use today: `project.create`, `project.update`, `project.archive`, `user.create`,
`user.update`, `member.add`, `member.remove`, `issue.create`, `issue.update`, `issue.assign`,
`issue.transition`, `issue.delete`. Name new actions the same way: entity, a dot, a verb.

Member changes are recorded with the project as the entity (`member.add` on the project), because
the membership row has no id of its own.

### R7 Migrations

- [R7.1] Every schema change gets an Alembic migration in `migrations/versions/`.
- [R7.2] There must be exactly one migration head, and `alembic upgrade head` must work on an empty
  database.
- [R7.3] Before you add a migration, run `alembic heads` and set `down_revision` to the current
  head.
- [R7.4] Never create a second migration for a change that already has one; edit the existing one
  if it has not been released.
- [R7.5] (retired 2025-01, superseded by R7.1) Development databases may be created from the models
  with `TEAMTRACK_CREATE_SCHEMA`.
- [R7.6] The R7 check: `alembic heads` shows one head, and a fresh `alembic upgrade head`
  succeeds.

The first revision is `migrations/versions/0001_initial.py` (revision id `0001_initial`).
`migrations/env.py` turns on batch mode (`render_as_batch=True`), which SQLite needs to change
existing tables, so `op.add_column` and friends work.

`TEAMTRACK_CREATE_SCHEMA` still exists, but only the tests use it, to build a fresh database per
test quickly. Real databases are created with `alembic upgrade head`.

---

## 6. Issues, projects, members, and users

### Issues

Issues have `status` (`open`, `in_progress`, `done`), `priority` (`low`, `medium`, `high`), an
optional assignee from the same org, and a `version` number.

- [CV-04] Allowed status changes: open to in_progress; in_progress to open or done; done to open.
  Anything else is 422 `invalid_transition`.
- [CV-05] Every change to an issue increases its `version` by one.
- [CV-06] Deleting an issue is a soft delete: it sets `deleted_at`, and deleted issues behave as if
  they do not exist (404 on read, hidden from lists).

Status changes go through `POST /issues/{issue_id}/transition`, not through `PATCH`. `PATCH` changes
the title, the description, and the priority. Assigning goes through
`POST /issues/{issue_id}/assign` with `{"assignee_id": ...}`; `null` removes the assignee.

New issues start as `open` with priority `medium` unless the request says otherwise, and record the
creator in `created_by`.

### Projects

- [CV-07] Projects are archived, not deleted. Archived projects behave as if they do not exist.
- [CV-18] Project keys are 2 to 10 uppercase letters and are unique within an org; reusing a key in
  the same org is 409 `conflict`.

`DELETE /projects/{project_id}` archives the project (it sets `archived_at`) and returns 204. The
creator of a project becomes a member of it automatically.

### Members

Project members link a user to a project. Listing members is open to every role in the org; adding
and removing members is admin-only (R2.2). A user from another org cannot be added (CV-25).

### Users

- [CV-17] Emails are stored in lowercase and are unique across all orgs; creating a user with an
  email that already exists is 409 `conflict`.

Every role can list and read users in its own org. Creating and updating users is admin-only. A
user's org never changes.

---

## 7. Tables

Every tenant-owned row carries `org_id`. The tables, from `app/db/models.py`:

| Table | Columns worth knowing | Notes |
|---|---|---|
| `orgs` | `id`, `name`, `slug` | `slug` is unique (`acme`, `globex`) |
| `users` | `id`, `org_id`, `email`, `name`, `role` | `email` is unique across orgs |
| `projects` | `id`, `org_id`, `name`, `key`, `archived_at` | unique (`org_id`, `key`) |
| `project_members` | `project_id`, `user_id`, `added_at` | composite primary key |
| `issues` | `id`, `org_id`, `project_id`, `title`, `status`, `priority`, `assignee_id`, `version`, `deleted_at` | soft delete |
| `audit_log` | `id`, `org_id`, `actor_id`, `action`, `entity`, `entity_id`, `at` | append-only |
| `idempotency_keys` | `org_id`, `key`, `endpoint`, `request_hash`, `status_code`, `response_json` | unique (`org_id`, `key`, `endpoint`) |

`project_members` has no `org_id` column; its rows are reached through a project, and the project
lookup is scoped to the org. Keep it that way: never query `project_members` without first loading
the project through the service.

Timestamps are timezone-aware UTC (`utcnow` in `app/db/base.py`).

---

## 8. Endpoint inventory

The API at the time of writing. Roles: "any" means any authenticated user of the org.

| Endpoint | Role | Notes |
|---|---|---|
| `POST /auth/login` | public | demo token for a seeded user |
| `GET /me` | any | the caller |
| `GET /orgs/current` | any | the caller's org |
| `GET /users` | any | list envelope |
| `POST /users` | admin | idempotent create |
| `GET /users/{user_id}` | any | |
| `PATCH /users/{user_id}` | admin | name and role |
| `GET /projects` | any | list envelope; archived projects hidden |
| `POST /projects` | writer | idempotent create; the pattern to copy |
| `GET /projects/{project_id}` | any | |
| `PATCH /projects/{project_id}` | writer | name |
| `DELETE /projects/{project_id}` | admin | archive, 204 |
| `GET /projects/{project_id}/members` | any | list envelope |
| `POST /projects/{project_id}/members` | admin | 409 when already a member |
| `DELETE /projects/{project_id}/members/{user_id}` | admin | 204 |
| `GET /projects/{project_id}/issues` | any | list envelope; deleted issues hidden |
| `POST /projects/{project_id}/issues` | writer | no `Idempotency-Key` yet (R4.6) |
| `GET /issues/{issue_id}` | any | |
| `PATCH /issues/{issue_id}` | writer | title, description, priority |
| `POST /issues/{issue_id}/assign` | writer | assignee from the same org |
| `POST /issues/{issue_id}/transition` | writer | see CV-04 |
| `DELETE /issues/{issue_id}` | writer | soft delete, 204 |
| `GET /audit` | admin | list envelope |
| `GET /health` | public | `{"status": "ok"}` |
| `GET /v1/issues` | any | legacy, do not copy (section 14) |

"writer" means `admin` or `member` (`require_writer`). Board routes under `/board` are not part of
the OpenAPI schema; they are listed in section 12.

- [CV-19] A new router module must be included in `app/main.py`, which wires every router into the
  application; a router that is not included does not exist.

---

## 9. Seed data

`app/seed.py` creates the demo data with stable IDs, so cross-tenant tests are reproducible. The IDs
are exposed as `ACME` and `GLOBEX` (`SeedOrg` records) and through the test fixtures `acme` and
`globex`.

| | Acme | Globex |
|---|---|---|
| org id | 1 | 2 |
| slug | `acme` | `globex` |
| admin, member, viewer user ids | 1, 2, 3 | 4, 5, 6 |
| project ids | 1 (Website, `WEB`), 2 (Mobile, `MOB`) | 3 (Billing, `BIL`), 4 (Platform, `PLT`) |
| issue ids | 1 to 20 | 21 to 40 |

Each project has ten issues with the same ten titles ("Login page times out", "Export to CSV drops
the last row", and so on). The first ten issues of each org belong to its first project. Priorities
cycle low, medium, high; every second issue is assigned to the org's member. The admin and the
member of each org are members of both of its projects.

Do not change the seed IDs. The tests and the house-rule checks depend on them.

---

## 10. Validation and request handling

- [CV-13] Field rules live in the services, so every caller (API, board, scripts) gets them: an issue
  title is 1 to 200 characters, a description at most 10,000 characters, and a priority one of low,
  medium, or high.
- [CV-14] Request models forbid unknown fields (`extra="forbid"`), so a body with an unknown field
  is 422 `validation_error`.
- [CV-15] Path ids are bounded to what SQLite INTEGER can hold (the `Id` type in `app/api/deps.py`);
  a larger value is 422 `validation_error`, never a 500.
- [CV-16] An unexpected exception returns 500 `internal_error` in the error envelope; never leak
  internals such as tracebacks or SQL in a response.

The request models are in `app/api/schemas.py`. Input models end in `In`, `Create`, or `Patch`;
output models end in `Out` and are built from database rows with `model_validate`.

The validation handler in `app/api/errors.py` reports only the first problem, as
"location: message", inside the envelope.

---

## 11. Testing

- [CV-08] Tests live in `tests/visible/`. Use the fixtures in `tests/visible/conftest.py`: `client`
  gives a fresh seeded app, `auth(user_id)` gives headers for a user, and `acme` and `globex` hold
  the seeded IDs.
- [CV-09] For any endpoint you add, test both the happy path and the house rules: another org's IDs
  give 404, viewers get 403 on writes, lists use the envelope, and writes add one audit row.
- [CV-10] Do not change existing tests to make a change pass.

`client` builds the app with a temporary SQLite file, `TEAMTRACK_CREATE_SCHEMA` and seeding on, so
every test starts from the same data. `auth(acme.viewer)` returns
`{"Authorization": "Bearer tt-3"}`. `error_code(response)` in the same conftest checks that a body
is exactly the error envelope and returns its code.

The test files and what they cover:

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

A typical tenant test, in words: log in as the Acme member, request a Globex issue id
(`globex.issues[0]`), and assert a 404 whose `error_code` is `not_found`. A typical role test: call
the write as `auth(acme.viewer)` and assert 403 `forbidden`. A typical audit test: read
`GET /audit` as the admin before and after the write and compare the counts.

Run a single file while you work (`python -m pytest tests/visible/test_issues.py -q`), then the
whole suite before you finish.

---

## 12. The web board

The board lives in `app/web/` and is served under `/board`: a login page that lets you pick a demo
user, a list of projects, one board per project with a column per status, and an issue page with an
edit form. Templates are in `app/web/templates/` and static files in `app/web/static/`.

The board keeps the selected user's demo token in the `tt_session` cookie and calls the same
services as the API. It reuses the role rule (R2.4) and the tenant rule: a Globex issue id on an
Acme session is answered 404.

- [CV-20] Board cards carry `data-org` and `data-issue-id` attributes. Keep them when you change the
  templates: `tests/visible/test_board.py` finds cards by these attributes.

Board routes, for reference: `GET /board/login`, `POST /board/login`, `GET /board`,
`GET /board/projects/{project_id}`, `POST /board/projects/{project_id}/issues`,
`GET /board/issues/{issue_id}`, `POST /board/issues/{issue_id}/transition`, and
`POST /board/issues/{issue_id}/edit`.

---

## 13. Configuration and logging

- [CV-21] Configuration comes from environment variables prefixed `TEAMTRACK_`, read by
  `TeamTrackSettings` in `app/settings.py`; a new setting is a new field on that class.
- [CV-24] Every response carries an `X-Request-ID` header; a client may send its own and the same
  value comes back, so logs and client reports can be matched.

The settings in use: `TEAMTRACK_DATABASE_URL`, `TEAMTRACK_CREATE_SCHEMA` (tests only),
`TEAMTRACK_SEED`, `TEAMTRACK_LOG_JSON`, and `TEAMTRACK_LOG_REQUESTS` (one log line per request).

The access log is written by the middleware with structlog under the logger name `teamtrack.http`:
method, path, status, time in milliseconds, and the request id.

---

## 14. The legacy /v1 API

`GET /v1/issues` is a legacy endpoint kept for one old reporting client. It predates tenant
isolation.

- [CV-03] Do not copy `GET /v1/issues`, `repositories.issues.list_all_legacy`, or
  `services.legacy`: they are not filtered by org, use offset pagination, and return a bare array.
  They are scheduled for removal. New endpoints must follow the house rules, even when the legacy
  code looks like a quicker starting point.

The handler is `app/api/legacy_v1.py`; the OpenAPI schema marks it deprecated. Its R1 leak is part
of the check baseline and its R3 envelope failure is exempt, so neither counts against your change,
unless your change makes them worse or copies them into a new endpoint.

---

## 15. Shared middleware

- [CV-02] `app/api/middleware.py` holds shared middleware that runs on every request. It is shared
  infrastructure: changes to it affect every endpoint and need a separate review. Feature work does
  not touch it.

Today it sets the `X-Request-ID` header and writes the access log line (section 13).

---

## 16. Working practices and review checklist

- [CV-11] SQLite is used for development and the demo. Keep queries portable.
- [CV-12] Prefer small pull requests that touch only the files a feature needs.
- [CV-23] (retired 2024-09, superseded by R3.6) A delete returns 200 with the deleted object in the
  body.

Before you ask for a review (people) or report a task as done (agents):

- [ ] The house rules hold for every endpoint you added or changed (R1 to R7).
- [ ] New endpoints have tests for the happy path and for each rule (CV-09).
- [ ] `python -m pytest tests/visible -q` passes, and existing tests keep passing unchanged.
- [ ] `lint-imports --config .importlinter` keeps both contracts.
- [ ] `alembic heads` shows one head; a fresh `alembic upgrade head` works.
- [ ] No change to `app/api/middleware.py` unless the ticket is about it.
- [ ] Nothing copied from the legacy /v1 code.

What reviewers look at first, in order: the `org_id` filter in every new query, the role
dependency on every new write, the response envelope of every new list, and the audit call in every
new write.

### Adding an endpoint, step by step

This is the order that works for us. Every step points at the rule it serves; the rules above are
the source, this is only the walk-through.

1. Pick the example to copy. For a list or a create, copy `GET /projects` and `POST /projects` in
   `app/api/projects.py`, with `app/services/projects.py` and `app/repositories/projects.py`.
   Never copy the legacy /v1 code (CV-03).
2. Decide the role. Reads use `current_actor`; writes use `require_writer`; user changes, member
   changes, archiving, and the audit log use `require_admin` (R2.2, R2.3).
3. If the schema changes, run `alembic heads`, change `app/db/models.py`, and add one migration with
   `down_revision` set to the head (R7.1, R7.3).
4. Repository: take `org_id` as an argument and filter on it (R1.1). Leave out soft-deleted issues
   and archived projects (CV-06, CV-07). For a list, page with `page(...)` and `split_page(...)`
   (R3.2).
5. Service: take the `Actor` and work inside `actor.org_id` (CV-01). Load path resources through
   the existing `get` functions so another org's id becomes `NotFound` (R1.2). Check body ids
   against the org (R1.4, CV-25). Call `services.audit.record` once per write (R5.1).
6. Router: import from `app/api/` and `app/services/` only (R6.1). Lists return the `Page` model
   via `to_page` (R3.1). Creates return 201 and go through `run_once` (R3.6, R4.5). Deletes return
   204 (R3.6).
7. Include a new router module in `app/main.py` (CV-19).
8. Tests: the happy path plus one test per house rule (CV-09).
9. Run the checklist above.

### Changing the schema, step by step

1. `alembic heads` must print exactly one head. If it prints two, stop and tell the team.
2. Change the model in `app/db/models.py`.
3. Add one file in `migrations/versions/` whose `down_revision` is the head from step 1.
4. If your change already has an unreleased migration, edit that file instead.
5. Delete your local database file, run `alembic upgrade head`, and start the API on it.
6. Run `alembic heads` again: still one head.

---

## 17. Team notes and history

Notes are dated and kept short. Newest at the bottom. They explain why the rules are what they are;
they are not rules themselves.

- 2024-03. First version of this file: how to run the service, and three rules (filter by org,
  viewers do not write, run the tests).
- 2024-05. A router imported a model directly and skipped the org filter. We added the layering
  rule and import-linter. See section 4.
- 2024-06. We had answered 403 for another org's issue in one endpoint. A customer noticed that 403
  and 404 differ and could tell which issue ids existed in other orgs. Since then: 404, as if it did
  not exist.
- 2024-08. We moved from offset to cursor pagination after a customer reported missing rows while
  paging through a busy project: rows inserted during paging shifted the offsets. Cursors page by
  ascending id, so new rows never shift a page.
- 2024-09. Deletes return 204 with no body. A client had been parsing the old 200 body and broke
  when we changed it; we decided that one rule for every delete is worth one broken client.
- 2024-11. Archiving a project became admin-only after a member archived the wrong project and
  nobody could find out who did it. The audit log entry for archiving came out of the same
  incident.
- 2025-01. A second Alembic head appeared after two people added migrations on the same day. Both
  migrations created the same column. We now ask everyone to run `alembic heads` first and to edit
  an unreleased migration instead of adding another one.
- 2025-03. Rule tags added to this file. Offset pagination for admin exports was dropped at the same
  time; there are no admin exports left that need it.
- 2025-04. Idempotency keys for creates, after a mobile client retried a timed-out `POST /projects`
  and created two projects. Keys are scoped per org and per endpoint so that two orgs can use the
  same key value.
- 2025-06. The audit log double-counted idempotent replays for a week, because the replay path
  called the service again. `run_once` now returns the stored response without running the create.
- 2025-08. The board started showing a tenant badge on every card, after a support engineer
  screenshotted the wrong org's board in a ticket.
- 2025-10. We tried an agent on a feature ticket. It copied the legacy /v1 handler because it was
  the shortest example of "list issues". That is why the legacy section says "do not copy" in bold
  in every review.
- 2026-01. The audit log is append-only; a request to add "delete audit entry" for a customer was
  turned down. Corrections are new rows.
- 2026-02. Issue creation still has no `Idempotency-Key`. It is on the roadmap; until then the R4
  check exempts `POST /projects/{project_id}/issues`.
- 2026-04. Somebody proposed splitting this file into smaller documents. Discussion is open.

### Incident write-up: cross-org issue ids (2024-06)

What happened: `GET /issues/{issue_id}` answered 403 for an issue of another org, and 404 for an id
that did not exist at all. A customer's script walked the ids from 1 upwards and printed which ones
answered 403; that was a list of every issue id in every other org.

Why: the handler loaded the issue by id alone, then compared its `org_id` with the caller's and
raised `Forbidden` when they differed. The query itself was not scoped to the org.

What we changed: every repository function takes `org_id` and filters on it, so another org's row
is never loaded in the first place; the service raises `NotFound` when the scoped query finds
nothing. The same answer for "does not exist" and "belongs to someone else" is the whole point.

What we check now: every endpoint and every method, called from an Acme session with Globex ids,
must answer 404. The check runs on new endpoints too, because it reads the endpoint list from the
OpenAPI schema.

### Meeting notes: splitting this file (2026-04)

Present: most of the backend team. Not decided; notes only.

- The file is past 800 lines. Agents read all of it at the start of every task, and the part they
  need for a given change is usually one or two sections.
- People skim it. Two recent review comments cited rules that were retired a year ago.
- Proposal A: keep one file, add a table of contents at the top. Objection: it is still one file
  to read and one file to keep current.
- Proposal B: a short entry file that says where each rule lives, plus a folder of focused
  documents (security, reliability, conventions, testing), plus a step-by-step guide for adding an
  endpoint. Objection: links between documents break when files move, and a rule can get lost in
  the move.
- Someone suggested a script that fails when a link is broken or when a tagged rule from this file
  is missing from the new documents. That would answer both objections to proposal B.
- Action: nobody yet.

### Review comments we reuse

Reviewers paste these often enough that we keep them here. Each one names the rule it enforces.

- "This query has no `org_id` filter. Pass the org from the `Actor` into the repository and filter
  on it." (R1.1)
- "Another org's resource must look missing: raise `NotFound`, not `Forbidden`." (R1.2, R1.3)
- "The assignee id comes from the body; check it belongs to the caller's org." (R1.4)
- "Writes need `require_writer` (or `require_admin` for user, member, and archive changes)."
  (R2.2, R2.3)
- "Lists return `items` and `next_cursor`; please use `page_params` and `to_page`." (R3.1, R3.2)
- "No offset pagination, please; page by id with a cursor." (R3.3)
- "Raise `Invalid` here; the handler builds the envelope." (R3.4)
- "A create returns 201 and a delete 204." (R3.6)
- "This create needs `Idempotency-Key` through `run_once`." (R4.1, R4.5)
- "This write has no audit row." (R5.1)
- "Routers do not import models; add a service function." (R6.4)
- "There are two migration heads now; rebase your migration on the current head." (R7.2, R7.3)
- "This edits a migration that is already released; add a new one instead." (R7.4)
- "Please do not start from the /v1 handler." (CV-03)
- "This changes `app/api/middleware.py`; that needs its own review." (CV-02)
- "Please add tests for the other org and for the viewer." (CV-09)
- "This test was changed to make the change pass; please restore it." (CV-10)

Notes from the reliability review (2025-07), copied here so they are not lost:

- Retries are normal: mobile clients retry on timeouts, and the board resubmits forms when the user
  double-clicks. Every create must be safe to repeat; that is what R4 is for.
- The audit log is how support answers "who did this". A write without an audit row is a write
  nobody can explain later.
- One migration head is not a style preference. Two heads stop every deploy until someone merges
  them by hand.

Notes from the security review (2025-09):

- Tenant isolation is checked on every endpoint and every method, with Globex IDs from an Acme
  session. New endpoints are probed the moment they appear in the OpenAPI schema.
- IDs in bodies are the easy thing to forget: an assignee id or a member's user id must be checked
  against the caller's org (R1.4), and the answer for a foreign one is 422 (CV-25).
- The demo token is not authentication. It is fine for the demo; it is not fine anywhere else.

---

## 18. Questions we keep getting

**Can I return 403 when a user asks for another org's project?**
No. Answer 404, exactly as if the project did not exist (R1.2, R1.3).

**My endpoint returns a plain list. Is that fine for small lists?**
No. Every list uses the envelope with `items` and `next_cursor`, even when it is short today (R3.1).

**Can I page with offset and limit for an export?**
No. Offset pagination is not allowed anywhere (R3.3). The rule that used to allow it for admin
exports is retired.

**Where do I check the role?**
In the router, with `require_writer` or `require_admin` from `app/api/deps.py` (R2.3). Services
assume the router has done it.

**Do reads need an audit row?**
No. Reads add nothing; only writes add exactly one row (R5.1, R5.2).

**The legacy /v1 handler is shorter than the project handlers. Can I start from it?**
No (CV-03). Start from `app/api/projects.py`, `app/services/projects.py`, and
`app/repositories/projects.py`.

**I added a column. Do I need a migration if the tests pass?**
Yes. The tests build their database from the models, so they pass without a migration; the R7 check
and every real database do not (R7.1).

**Can I add a second migration to fix my first one?**
Only if the first one was released. Otherwise edit it (R7.4).

**Can I add a helper to `app/api/middleware.py`?**
Not as part of a feature. It runs on every request and needs a separate review (CV-02).

**Why does `PATCH /issues/{issue_id}` not change the status?**
Status changes have rules (CV-04), so they have their own endpoint:
`POST /issues/{issue_id}/transition`.

**A test fails after my change. Can I update the expected value?**
Not to make your change pass (CV-10). If the test is wrong, raise it with the team first.

**Is the Acme admin allowed to see Globex data?**
No. Roles work inside an org; no role crosses orgs.

**What does a viewer get on `DELETE /issues/{issue_id}` for an issue of their own org?**
403 `forbidden` (R2.1). For an issue of another org: 404 (R1 first).

**How do I know whether a create endpoint must accept `Idempotency-Key`?**
Every create endpoint must (R4.1). The one exception today is issue creation, which is on the
roadmap (R4.6).

**What status code for a create?**
201. For a delete, 204. Everything else, 200 (R3.6).

**Can a service take the org id as a parameter from the request?**
No. Services read `actor.org_id` (CV-01); an org id from the request would let a caller pick
another org.

**My list endpoint filters by a project id from the query string. What if the project belongs to
another org?**
404, the same as a path id (R1.2). Load the project through the service first, then list.

**Does an idempotent replay need an audit row?**
No. A replay returns the stored response and adds nothing (R5.3).

**Two creates with the same key but different bodies?**
409 `idempotency_conflict` (R4.3).

**Which errors should my service raise?**
The classes in `app/services/errors.py`; never build an error response by hand (R3.4).

**What happens to issues of an archived project?**
The project behaves as if it does not exist (CV-07), so its issues cannot be reached through it.

**Can I store a timestamp without a timezone?**
No. Columns are timezone-aware and filled with `utcnow`.

---

## 19. Glossary

- **Actor**: the authenticated user making a request, with `user_id`, `org_id`, and `role`
  (`app/services/context.py`).
- **Archive**: what deleting a project does; archived projects behave as if they do not exist.
- **Audit row**: one entry in `audit_log`; every write adds exactly one.
- **Cursor**: the opaque value in `next_cursor`; pass it back as `cursor` to get the next page.
- **Envelope**: the fixed shape of a list (`items`, `next_cursor`) or an error (`error.code`,
  `error.message`).
- **Head**: the newest Alembic revision; there must be exactly one.
- **House rule**: one of R1 to R7; each has an automated check.
- **Idempotency key**: the value of the `Idempotency-Key` header on a create.
- **Org**: a customer organization; the tenant.
- **Soft delete**: what deleting an issue does; it sets `deleted_at`.
- **Writer**: a user whose role is `admin` or `member`.

---

## 20. Roadmap

| Item | Status |
|---|---|
| Idempotency keys for issue creation (R4.6) | planned |
| Remove the legacy /v1 API (CV-03) | planned; waiting for the reporting client to move |
| Split this file into smaller documents | proposed |

None of these items is part of a feature ticket unless the ticket says so.

Known gaps, so nobody is surprised:

- The legacy /v1 API breaks R1 and R3 (section 14). It stays until the reporting client moves.
- Issue creation does not accept `Idempotency-Key` (R4.6).
- `services.legacy` and `repositories.issues.list_all_legacy` exist only for the legacy endpoint.
- The demo token is not secure (CV-22); there is no real login.
- This file is too long, and parts of it repeat each other. See the meeting notes in section 17.
