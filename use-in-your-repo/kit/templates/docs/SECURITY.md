<!-- REPLACE: TeamTrack's security rules, kept as the example. Keep the shape: each rule says what, why, how it is checked, and which code shows the pattern. Delete rules that do not apply to your repository. -->
# Security

Who may see and change data. Two house rules live here: House rule 1: Tenant isolation and House
rule 2: Roles. They apply to every endpoint, including new ones. Automated checks discover endpoints from the OpenAPI schema,
so a new endpoint is checked the moment it exists.

## House rule 1: Tenant isolation

<!-- REPLACE: your tenant or owner boundary (TeamTrack: the org). Delete `R1` (tenant isolation) if every caller may see all data. The check is `shipharness check --rules R1` with your adapter (docs/house-rules.md). -->
No org may see or change another org's data.

- Every query on customer data filters by the caller's `org_id`. Services work only inside
  `actor.org_id`; repositories take `org_id` as an explicit argument (`ARCHITECTURE.md`).
- If a user asks for a resource that belongs to another org, respond 404 not_found, exactly as if it
  did not exist.
- Never respond 403 for another org's resource, because that tells the caller it exists.
- When an endpoint takes the ID of another object in its body (for example an assignee), check that
  the object belongs to the caller's org.

In code: raise `NotFound` from `app/services/errors.py` when the lookup scoped to `actor.org_id`
finds nothing.

The check: for every endpoint and method, a request as an Acme user with Globex IDs must return 404.

## House rule 2: Roles

<!-- REPLACE: your roles and which of them may write. Delete `R2` (roles) if every caller may write. -->
Roles are `admin`, `member`, and `viewer`.

- Viewers can read but never write: every POST, PUT, PATCH, and DELETE must return 403 forbidden for
  a viewer.
- Some writes are admin-only: creating and updating users, adding and removing project members,
  archiving projects, and reading the audit log.
- Use the dependencies in `app/api/deps.py` (`require_writer`, `require_admin`) rather than checking
  roles by hand.

| Endpoint kind | Dependency |
|---|---|
| read | `current_actor` |
| write | `require_writer` |
| admin-only write or the audit log | `require_admin` |

The check: every write endpoint called as a viewer must return 403.

## Authentication

<!-- REPLACE: how callers authenticate in development. Never write a real key or password here. -->
Demo login: `POST /auth/login` with `{"email": "admin@acme.test"}` returns a token. Send it as
`Authorization: Bearer <token>`. Demo users exist for each role in each org (`admin@`, `member@`,
`viewer@` at `acme.test` and `globex.test`). The demo token format is not secure and exists only for
local use.

## Shared middleware

<!-- REPLACE: shared code that needs a separate review. Delete this section if it does not apply. -->
`app/api/middleware.py` runs on every request. Changes to it affect every endpoint and need a separate
review; feature work should not touch it.

## Legacy

<!-- REPLACE: legacy code that breaks these rules. Delete this section if it does not apply. -->
`GET /v1/issues` predates tenant isolation and is not filtered by org. Do not copy it
(`docs/QUALITY_SCORE.md`).
