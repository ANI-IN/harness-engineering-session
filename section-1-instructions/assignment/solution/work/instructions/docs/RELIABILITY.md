# Reliability

Writes that are safe to repeat, a complete audit trail, and a schema that always migrates. Three
house rules live here: R4 Idempotent creates, R5 Audit log, and R7 Migrations. They apply to every
endpoint, including new ones.

Retries are normal: mobile clients retry on timeouts, and the board resubmits forms when the user
double-clicks. The audit log is how support answers "who did this". Two migration heads stop every
deploy until someone merges them by hand.

## R4 Idempotent creates

- [R4.1] Create endpoints accept an `Idempotency-Key` header.
- [R4.2] The same key with the same body returns the first response and creates nothing new.
- [R4.3] The same key with a different body returns 409 `idempotency_conflict`.
- [R4.4] Keys are scoped per org and per endpoint.
- [R4.5] Use `services.idempotency.run_once`; see `POST /projects` for the pattern. The service
  function takes `commit: bool = True` and the router passes `commit=False`, so `run_once` commits
  once.
- [R4.6] Issue creation does not support keys yet; that is on the roadmap (`docs/PLANS.md`).
- [R4.7] The R4 check: a duplicate POST with the same key must leave exactly one new record.

How the pattern in `app/api/projects.py` fits together: the router reads the `Idempotency-Key`
header, defines a `create()` function that calls the service with `commit=False` and returns the
response body, and passes both to `idempotency.run_once` with the endpoint name (`"POST /projects"`)
and the request body. `run_once` stores the response under the org, the key, and the endpoint, then
commits. `POST /users` follows the same pattern. Adding a project member is a create too, but a
second identical request is answered 409 `conflict`, so it never makes a second record.

## R5 Audit log

- [R5.1] Every write adds exactly one row to the audit log, with the actor, an action name such as
  `issue.create`, the entity type, and its id.
- [R5.2] Reads add nothing.
- [R5.3] An idempotent replay adds nothing.
- [R5.4] Use `services.audit.record`.
- [R5.5] The audit log is append-only; there is no endpoint to edit or delete audit rows.
- [R5.6] The R5 check: count audit rows before and after each write.

Action names in use: `project.create`, `project.update`, `project.archive`, `user.create`,
`user.update`, `member.add`, `member.remove`, `issue.create`, `issue.update`, `issue.assign`,
`issue.transition`, `issue.delete`. Name new actions the same way: entity, a dot, a verb. Member
changes are recorded with the project as the entity, because the membership row has no id of its
own. Reading the audit log (`GET /audit`) is admin-only (R2.2, `docs/SECURITY.md`).

## R7 Migrations

- [R7.1] Every schema change gets an Alembic migration in `migrations/versions/`.
- [R7.2] There must be exactly one migration head, and `alembic upgrade head` must work on an empty
  database.
- [R7.3] Before you add a migration, run `alembic heads` and set `down_revision` to the current head.
- [R7.4] Never create a second migration for a change that already has one; edit the existing one if
  it has not been released.
- [R7.6] The R7 check: `alembic heads` shows one head, and a fresh `alembic upgrade head` succeeds.

Changing the schema, step by step (from the TeamTrack folder):

1. `alembic heads` must print exactly one head. If it prints two, stop and tell the team.
2. Change the model in `app/db/models.py`.
3. Add one file in `migrations/versions/` whose `down_revision` is the head from step 1.
4. If your change already has an unreleased migration, edit that file instead.
5. Delete your local database file, run `alembic upgrade head`, and start the API on it.
6. Run `alembic heads` again: still one head.

The tests build their database from the models (`TEAMTRACK_CREATE_SCHEMA`), so they pass without a
migration; the R7 check and every real database do not. The first revision is
`migrations/versions/0001_initial.py` (revision id `0001_initial`). `migrations/env.py` turns on
batch mode (`render_as_batch=True`), which SQLite needs to change existing tables.

## Portability

- [CV-11] SQLite is used for development and the demo. Keep queries portable.
