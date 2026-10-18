<!-- REPLACE: TeamTrack's quality grades, kept as the example. Grade each domain and layer of your repository and record the known gaps. -->
# Quality score

Grades for each product domain and architectural layer, and the gaps we track. Update a row when a
change closes or opens a gap.

Grades: **meets rules** (no gap recorded), **gap** (a known shortfall that is on the roadmap),
**do not copy** (breaks house rules; kept only until removal).

## Product domains

<!-- REPLACE: one row per product domain: meets rules, gap, or do not copy. -->
| Domain | Grade | Notes |
|---|---|---|
| Projects | meets rules | `POST /projects` is the pattern for idempotent creates (House rule 4: Safe retries). Projects are archived, not deleted. |
| Users | meets rules | Creating and updating users is admin-only (House rule 2: Roles). |
| Project members | meets rules | Adding and removing members is admin-only (House rule 2). |
| Issues | check | Issue creation accepts keys once Feature 3: Safe retries for issue creation is in place (House rule 4, `docs/features/f3.md`); check `app/api/issues.py`. |
| Audit log | meets rules | Append-only; reading it is admin-only. |
| Legacy /v1 API | do not copy | See "Legacy /v1 API" below. |

## Architectural layers

<!-- REPLACE: one row per layer or package. -->
| Layer | Grade | Notes |
|---|---|---|
| `app/api/` | meets rules | Never imports `app.db` (House rule 6: Layering). `app/api/middleware.py` is shared; feature work does not touch it. |
| `app/web/` | meets rules | Never imports `app.db` (House rule 6). |
| `app/services/` | meets rules, except `services.legacy` | Every function takes an `Actor` and works inside `actor.org_id`. |
| `app/repositories/` | meets rules, except `repositories.issues.list_all_legacy` | Every customer query takes `org_id`. |
| `app/db/` | meets rules | Schema changes go through Alembic (House rule 7: Migrations). |

## Legacy /v1 API

<!-- REPLACE: the legacy code agents must not copy. Delete this section if it does not apply. -->
`GET /v1/issues` is a legacy endpoint kept for one old reporting client. It predates tenant isolation:
it is not filtered by org, uses offset pagination, and returns a bare array. It is scheduled for
removal. Do not copy it. New endpoints must follow the house rules, even when the legacy code looks
like a quicker starting point. The same applies to `repositories.issues.list_all_legacy` and
`services.legacy`.

## Testing

How we keep the grades honest.

<!-- REPLACE: where your tests live, the fixtures to use, what every change must test, and the test command. -->
- Tests live in `tests/visible/`.
- Use the fixtures in `tests/visible/conftest.py`: `client` gives a fresh seeded app; `auth(user_id)`
  gives headers for a user; `acme` and `globex` hold the seeded IDs.
- For any endpoint you add, test both the happy path and the house rules: another org's IDs give 404,
  viewers get 403 on writes, lists use the envelope, writes add one audit row.
- Do not change existing tests to make a change pass.
- Run them with `python -m pytest tests/visible -q` from the TeamTrack folder.

Automated checks for House rules 1 to 7 discover endpoints from the OpenAPI schema, so a new endpoint is checked
the moment it exists. Each rule's check is described next to the rule (`docs/SECURITY.md`,
`docs/RELIABILITY.md`, `docs/design-docs/api-conventions.md`, `ARCHITECTURE.md`).
