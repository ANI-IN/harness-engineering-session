# Reliability

Writes that are safe to repeat, a complete audit trail, and a schema that always migrates. Three house
rules live here: House rule 4: Safe retries, House rule 5: Audit log, and House rule 7: Migrations.
They apply to every endpoint, including new ones.

## House rule 4: Safe retries

- Create endpoints accept an `Idempotency-Key` header.
- The same key with the same body returns the first response and creates nothing new.
- The same key with a different body returns 409 idempotency_conflict.
- Keys are scoped per org and per endpoint.
- Use `services.idempotency.run_once`; see `POST /projects` for the pattern.
- Issue creation accepts keys once Feature 3: Safe retries for issue creation is in place
  (`docs/features/f3.md`); check `app/api/issues.py` before relying on it.

How the pattern in `app/api/projects.py` fits together: the router reads the `Idempotency-Key`
header, defines a `create()` function that calls the service with `commit=False` and returns the
response body, and passes both to `idempotency.run_once` with the endpoint name (`"POST /projects"`)
and the request body. `run_once` commits and returns the status and body.

The check: a duplicate POST with the same key must leave exactly one new record.

## House rule 5: Audit log

- Every write adds exactly one row to the audit log, with the actor, an action name such as
  `issue.create`, the entity type, and its id.
- Reads add nothing.
- An idempotent replay adds nothing.
- Use `services.audit.record`.
- The audit log is append-only; there is no endpoint to edit or delete audit rows.
- Reading the audit log is admin-only (House rule 2: Roles, `docs/SECURITY.md`).

The check: count audit rows before and after each write.

## House rule 7: Migrations

- Every schema change gets an Alembic migration in `migrations/versions/`.
- There must be exactly one migration head, and `alembic upgrade head` must work on an empty
  database.
- Before you add a migration, run `alembic heads` and set `down_revision` to the current head.
- Never create a second migration for a change that already has one; edit the existing one if it has
  not been released.

Commands (from the TeamTrack folder): `alembic heads` shows the heads; `alembic upgrade head` creates
or upgrades the database. Notes on Alembic: `docs/references/alembic-llms.txt`.

The check: `alembic heads` shows one head, and a fresh `alembic upgrade head` succeeds.

## Portability

SQLite is used for development and the demo. Keep queries portable.
