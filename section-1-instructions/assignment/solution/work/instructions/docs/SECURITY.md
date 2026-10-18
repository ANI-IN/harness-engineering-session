# Security

Who may see and change which data. Two house rules live here, R1 Tenant isolation and R2 Roles, with
the conventions that go with them. They apply to every endpoint, including new ones, and to the
board.

Many customers share one database, so every row that belongs to a customer carries an `org_id`. If a
query forgets the `org_id` filter, one customer sees another customer's data: the worst bug this
service can have.

## R1 Tenant isolation

No org may see or change another org's data.

- [R1.1] Every query on customer data filters by the caller's `org_id`. Repositories take `org_id` as
  an explicit argument and filter on it; a repository function never guesses the org.
- [R1.2] If a user asks for a resource that belongs to another org, respond 404 `not_found`, exactly
  as if it did not exist.
- [R1.3] Never respond 403 for another org's resource, because a 403 tells the caller that the
  resource exists.
- [R1.4] When an endpoint takes the ID of another object in its body (for example an assignee, or a
  user to add as a project member), check that the object belongs to the caller's org before you use
  it.
- [R1.5] Lists only ever contain rows of the caller's org, including lists that span several
  projects.
- [R1.6] The R1 check: for every endpoint and method, a request as an Acme user with Globex IDs must
  return 404.

How the code does it: services call `projects.get(session, actor, project_id)` or `issues.get(...)`,
which raise `NotFound` when the row is missing or belongs to another org. Services never take an
`org_id` from the request; they read `actor.org_id` (CV-01, `ARCHITECTURE.md`). An id in the query
string (for example a project filter on a list) is treated like a path id: load it through the
service first, so another org's id is 404.

A body id from another org is not a missing path resource, so it gets its own answer:

- [CV-25] An ID in a request body that does not belong to the caller's org is answered 422, with code
  `invalid_assignee` for issue assignees and `invalid_user` for project members.

The check counts a violation whenever an Acme request with a Globex id gets anything other than 404,
and a leak when a 2xx body contains Globex data. The legacy `/v1/issues` leak is part of the check
baseline (`docs/QUALITY_SCORE.md`).

## R2 Roles

- [R2.1] Roles are `admin`, `member`, and `viewer`. Viewers can read but never write: every POST,
  PUT, PATCH, and DELETE must return 403 forbidden for a viewer.
- [R2.2] Some writes are admin-only: creating and updating users, adding and removing project
  members, and archiving projects. Reading the audit log is admin-only as well.
- [R2.3] Use the dependencies in `app/api/deps.py` (`current_actor`, `require_writer`,
  `require_admin`) rather than checking roles by hand.
- [R2.4] The board follows the same rule: a viewer who tries to create, edit, or move an issue on the
  board gets 403.
- [R2.6] The R2 check: every write endpoint called as a viewer must return 403.

`current_actor` authenticates the bearer token and returns the `Actor`; `require_writer` lets `admin`
and `member` through; `require_admin` lets only `admin` through. A missing or invalid token is 401
`unauthorized` before any role check runs. Roles work inside an org; no role crosses orgs.

R1 comes before R2: an Acme viewer who asks to change a Globex issue gets 404, not 403, because the
issue does not exist for them.

## Demo authentication

`POST /auth/login` with `{"email": "admin@acme.test"}` returns a token; send it as
`Authorization: Bearer <token>`. Demo users exist for each role in each org (`admin@`, `member@`,
`viewer@` at `acme.test` and `globex.test`).

- [CV-22] The demo token is `tt-<user id>` and is not secure: it exists only for local use and demos.
  Never build anything that trusts it outside a laptop.

## Why these rules

- 2024-06: one endpoint answered 403 for another org's issue and 404 for a missing one. A customer's
  script walked the ids and printed every issue id that existed in other orgs. Since then every
  repository function takes `org_id`, another org's row is never loaded, and the answer is 404.
- Ids in bodies are the easy thing to forget: an assignee id or a member's user id must be checked
  against the caller's org (R1.4), and a foreign one is 422 (CV-25).
- Archiving became admin-only after a member archived the wrong project (2024-11).

More history: [design-docs/decisions.md](design-docs/decisions.md).
