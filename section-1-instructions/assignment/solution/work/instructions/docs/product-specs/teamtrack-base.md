# TeamTrack base product

What TeamTrack does from the user's side: orgs, users and roles, projects, members, issues, and the
audit log. Access rules are in `docs/SECURITY.md`; response shapes in
`docs/design-docs/api-conventions.md`.

Each customer is an organization ("org"). The demo database has two orgs, Acme and Globex.

## Issues

Issues have `status` (`open`, `in_progress`, `done`), `priority` (`low`, `medium`, `high`), an
optional assignee from the same org, and a `version` number.

- [CV-04] Allowed status changes: open to in_progress; in_progress to open or done; done to open.
  Anything else is 422 `invalid_transition`.
- [CV-05] Every change to an issue increases its `version` by one.
- [CV-06] Deleting an issue is a soft delete: it sets `deleted_at`, and deleted issues behave as if
  they do not exist (404 on read, hidden from lists).

Status changes go through `POST /issues/{issue_id}/transition`, not `PATCH`; `PATCH` changes the
title, the description, and the priority. Assigning goes through `POST /issues/{issue_id}/assign`
with `{"assignee_id": ...}`; `null` removes the assignee. New issues start as `open` with priority
`medium` unless the request says otherwise, and record the creator in `created_by`.

## Projects

- [CV-07] Projects are archived, not deleted. Archived projects behave as if they do not exist.
- [CV-18] Project keys are 2 to 10 uppercase letters and are unique within an org; reusing a key in
  the same org is 409 `conflict`.

`DELETE /projects/{project_id}` archives the project (it sets `archived_at`) and returns 204. The
creator of a project becomes a member of it automatically. The issues of an archived project cannot
be reached through it.

## Members and users

Project members link a user to a project. Every role can list members; adding and removing members
is admin-only. A user from another org cannot be added (CV-25, `docs/SECURITY.md`).

- [CV-17] Emails are stored in lowercase and are unique across all orgs; creating a user with an
  email that already exists is 409 `conflict`.

Every role can list and read users in its own org. Creating and updating users is admin-only. A
user's org never changes.

## Endpoints

"any" means any authenticated user of the org; "writer" means `admin` or `member`.

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
| `GET /v1/issues` | any | legacy, do not copy (`docs/QUALITY_SCORE.md`) |

Board routes under `/board` are not part of the OpenAPI schema: `GET /board/login`,
`POST /board/login`, `GET /board`, `GET /board/projects/{project_id}`,
`POST /board/projects/{project_id}/issues`, `GET /board/issues/{issue_id}`,
`POST /board/issues/{issue_id}/transition`, and `POST /board/issues/{issue_id}/edit`.

## Seed data

`app/seed.py` creates the demo data with stable ids, exposed as `ACME` and `GLOBEX` (`SeedOrg`
records) and through the test fixtures `acme` and `globex`. Do not change the seed ids: the tests and
the house-rule checks depend on them.

| | Acme | Globex |
|---|---|---|
| org id | 1 | 2 |
| slug | `acme` | `globex` |
| admin, member, viewer user ids | 1, 2, 3 | 4, 5, 6 |
| project ids | 1 (Website, `WEB`), 2 (Mobile, `MOB`) | 3 (Billing, `BIL`), 4 (Platform, `PLT`) |
| issue ids | 1 to 20 | 21 to 40 |

Each project has ten issues with the same ten titles. The first ten issues of each org belong to its
first project. Priorities cycle low, medium, high; every second issue is assigned to the org's
member. The admin and the member of each org are members of both of its projects.
