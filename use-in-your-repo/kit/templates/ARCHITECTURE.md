<!-- REPLACE: TeamTrack's architecture map, kept as the example. Keep this file at the repository root, next to AGENTS.md: domains, layers, and what each layer may import. Rewrite each section for your repository, then delete the REPLACE lines. -->
# Architecture

A top-level map of TeamTrack's domains and package layering. The rules that every endpoint follows
are in `docs/SECURITY.md`, `docs/RELIABILITY.md`, and `docs/design-docs/api-conventions.md`.

## Domains

<!-- REPLACE: your domains: what the product holds, who owns each piece of data, and where product behaviour is specified. -->
TeamTrack is a multi-tenant issue tracker: an HTTP API (FastAPI) plus a small web board (Jinja2 and
HTMX). Each customer is an organization ("org"). Orgs have users, projects, project members, issues,
and an audit log. Many customers share one database, so every row that belongs to a customer carries
an `org_id`. The demo database has two orgs, Acme and Globex. Product behaviour (issue statuses,
transitions, soft delete, archived projects) is in `docs/product-specs/teamtrack-base.md`.

## Layers

The code is layered. A layer may only call the layer below it.

<!-- REPLACE: your layers from top to bottom, the package of each, and what each may use. If your code has no layers, say how it is split instead. -->
| Layer | Package | What it does | What it may use |
|---|---|---|---|
| web | `app/web/` | the web board, routes under `/board` (Jinja2 and HTMX) | `app/api/deps.py`, services |
| api | `app/api/` | routers, request and response schemas, dependencies, error handling | services |
| services | `app/services/` | business logic | repositories |
| repositories | `app/repositories/` | database queries | `app/db/` |
| db | `app/db/` | SQLAlchemy models and engine setup | nothing above it |

- Routers call services. The api package never imports `app.db`; it gets data only through services.
  If you need data in a router, add or extend a service function. Do not import models or sessions
  into `app/api/`.
- Every service function takes an `Actor` (the authenticated user, with `user_id`, `org_id`, `role`)
  and works only inside `actor.org_id`.
- Every repository query on customer data takes `org_id` as an explicit argument and filters on it.
- The web board in `app/web/` sits above `app/api/`. Like the api package, it never imports `app.db`.

`app/main.py` wires everything together. `app/seed.py` creates the demo data.

## House rule 6: Layering

<!-- REPLACE: your layering rule and the command that checks it. The same contract goes into layering_contract() in harness/shipharness_adapter.py for `shipharness check --rules R6` (`R6` is the id of House rule 6). -->
`app/api` never imports `app/db`, and neither does `app/web`.

The check: the import-linter contract. Run `lint-imports --config .importlinter` from the TeamTrack
folder. The contract in `.importlinter` lists the layers in the order of the table above.

## Shared infrastructure

<!-- REPLACE: shared code that feature work must not change. Delete this section if it does not apply. -->
`app/api/middleware.py` holds shared middleware that runs on every request. Changes to it affect
every endpoint and need a separate review; feature work should not touch it.

## Data and migrations

<!-- REPLACE: your database and migration tool. Delete this section if it does not apply. -->
SQLite is used for development and the demo. Keep queries portable. Every schema change gets an
Alembic migration in `migrations/versions/` (House rule 7: Migrations, `docs/RELIABILITY.md`).

## Legacy code

<!-- REPLACE: legacy code agents must not copy, and what to copy instead. Delete this section if it does not apply. -->
`GET /v1/issues`, `repositories.issues.list_all_legacy`, and `services.legacy` predate tenant
isolation. They are scheduled for removal. Do not copy them (`docs/QUALITY_SCORE.md`).
