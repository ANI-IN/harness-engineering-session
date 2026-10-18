---
name: add-endpoint
description: Add or change a TeamTrack HTTP endpoint so it follows House rules 1 to 7 (tenant isolation, roles, API conventions with list and error envelopes, safe retries for creates, one audit row per write, layering, migrations) and ships with tests. Use when a ticket adds a route, changes a route's behaviour, or adds a field that needs a schema change.
---

# Add a TeamTrack endpoint

Work through the steps in order. Each step names the rule it satisfies and the document that holds
the full rule. Automated checks find every endpoint in the OpenAPI schema, so a new endpoint is
checked against House rules 1 to 7 the moment it exists.

## 0. Start from the right example

- Do not start from `GET /v1/issues` (`app/api/legacy_v1.py`), `repositories.issues.list_all_legacy`,
  or `services.legacy`. They are not filtered by org, use offset pagination, return a bare array, and
  are scheduled for removal.
- Start from `app/api/projects.py`, `app/services/projects.py`, and `app/repositories/projects.py`.
  `POST /projects` is the pattern for idempotent creates.

## 1. Decide what the endpoint is

Answer these before writing code:

| Question | Where the answer leads |
|---|---|
| Read or write? | Reads use `current_actor`; writes use `require_writer` (House rule 2: Roles). |
| Admin-only? Creating and updating users, adding and removing project members, archiving projects, and reading the audit log are. | Use `require_admin` (House rule 2). |
| Does it return a list? | List envelope and cursor pagination (House rule 3: API conventions). |
| Does it create something? | 201, `Idempotency-Key`, `run_once` (House rule 3, House rule 4: Safe retries). |
| Does it delete something? | 204 (House rule 3). Issues are soft-deleted and projects archived (`docs/product-specs/teamtrack-base.md`). |
| Does its body carry another object's ID (for example an assignee)? | Check that the object belongs to the caller's org (House rule 1: Tenant isolation). |
| Does it need a new table or column? | One Alembic migration (House rule 7: Migrations), step 2. |

Full rules: `docs/SECURITY.md` (House rules 1 and 2), `docs/design-docs/api-conventions.md`
(House rule 3), `docs/RELIABILITY.md` (House rules 4, 5, and 7), `ARCHITECTURE.md` (House rule 6:
Layering).

## 2. Schema change (House rule 7), only if needed

1. Run `alembic heads` from the TeamTrack folder. There must be exactly one head.
2. Change the model in `app/db/models.py`.
3. Add one migration in `migrations/versions/` with `down_revision` set to the current head.
4. If this change already has a migration that has not been released, edit it instead of adding a
   second one.
5. Check: `alembic heads` shows one head, and `alembic upgrade head` works on an empty database.

Alembic notes: `docs/references/alembic-llms.txt`.

## 3. Repository (House rule 1)

- Every query on customer data takes `org_id` as an explicit argument and filters on it.
- For a list, page by ascending id with the helpers in `app/repositories/common.py` (`page`,
  `split_page`), as `app/repositories/projects.py` does in `list_page`.
- Archived projects and soft-deleted issues behave as if they do not exist: filter them out.

## 4. Service (House rule 1, House rule 5: Audit log)

- The function takes the session and an `Actor`, and works only inside `actor.org_id`.
- If the resource is missing or belongs to another org, raise `NotFound` from
  `app/services/errors.py`. Never raise `Forbidden` for another org's resource.
- For an ID in the body, look it up scoped to `actor.org_id` (see `_check_assignee` in
  `app/services/issues.py`).
- Every write calls `services.audit.record` exactly once, with an action name such as
  `issue.create`, the entity type, and its id. Reads record nothing.
- A create used with `run_once` takes `commit: bool = True` and the router passes `commit=False`,
  so `run_once` commits once and an idempotent replay adds no audit row.

## 5. Router (House rules 2, 3, 4, and 6)

- Import only from `app/api/` and `app/services/`. Never import `app.db` (House rule 6).
- Role dependency from `app/api/deps.py`: `current_actor`, `require_writer`, or `require_admin`.
- Lists: `page_params`, `decode_cursor`, and `to_page` from `app/api/pagination.py`, with a `Page`
  response model, as `list_projects` in `app/api/projects.py` does.
- Errors: raise the classes in `app/services/errors.py`; the handlers in `app/api/errors.py` produce
  `{"error": {"code": "...", "message": "..."}}`.
- Status codes: 201 for creates, 204 for deletes, 200 otherwise.
- Creates: read the `Idempotency-Key` header and call `idempotency.run_once` with the endpoint name
  (for example `"POST /projects"`), the request body, and a `create()` function, as
  `create_project` in `app/api/projects.py` does.
- A new router module is included in `app/main.py`, which wires everything together.
- Do not touch `app/api/middleware.py`.

## 6. Tests

Add tests in `tests/visible/` for the happy path and for each rule: another org's IDs give 404,
viewers get 403 on writes, lists use the envelope, writes add one audit row. Patterns that match the
existing fixtures are in [references/tests.md](references/tests.md). Do not change existing tests to
make a change pass.

## 7. Check before you finish

From the TeamTrack folder:

```
python -m pytest tests/visible -q
lint-imports --config .importlinter
alembic heads
```

All tests pass (existing tests keep passing, unchanged), both import contracts are kept, and there is
one migration head.
