---
name: add-list-endpoint
description: >
  Add or change a TeamTrack list endpoint (a GET that returns many rows, with optional filters) so
  it only ever returns the caller's org's rows (house rule R1), uses cursor pagination and the
  items and next_cursor envelope (R3), and ships with tests for both. Use when a ticket adds a
  list, a search, an org-wide view, or a new filter on an existing list.
license: MIT
---

# Add a TeamTrack list endpoint

Build a list endpoint that is scoped to the caller's org, pages with a cursor, answers another org's
ids with 404, and has tests that prove it. The result passes the R1 and R3 checks the moment the
endpoint appears in the OpenAPI schema.

## When to use

- A ticket asks for a new list or search ("list all issues in my org", "filter by status"), or a new
  filter on an existing list.
- Not for writes: for a create, update, or delete, read `docs/RELIABILITY.md` (R4, R5) and
  `docs/SECURITY.md` (R2) instead.

## Steps

1. Start from `GET /projects`: `list_projects` in `app/api/projects.py`, with
   `app/services/projects.py` and `app/repositories/projects.py`. Do not start from the legacy
   `GET /v1/issues` handler, `repositories.issues.list_all_legacy`, or `services.legacy` (CV-03).
2. Repository: write one function that takes `org_id` as an explicit argument and filters on it
   (R1.1). Leave out soft-deleted issues and archived projects (CV-06, CV-07). Page with `page(...)`
   and `split_page(...)` from `app/repositories/common.py` (R3.2). Never use offset pagination
   (R3.3).
3. Service: take the `Actor` and pass `actor.org_id` to the repository (CV-01). For every id that
   comes from the path or the query string (a project id, an assignee id), load it through the
   existing service `get` function first, so another org's id raises `NotFound` and becomes 404
   (R1.2, R1.3). Rows of other orgs never appear, even when the list spans several projects (R1.5).
4. Router: `params: PageParams = Depends(page_params)`, `current_actor` for reads (R2.3),
   `decode_cursor(params.cursor)`, and return `to_page` with a `Page` response model (R3.1). Import only from `app/api/` and `app/services/` (R6.1). A new router
   module goes into `app/main.py` (CV-19).
5. Invalid filter values: raise `Invalid` from `app/services/errors.py`, or let the request model
   reject them; both give 422 `validation_error` in the envelope (R3.4, R3.5).
6. Tests: follow [references/tests.md](references/tests.md). Do not change existing tests (CV-10).
7. Run the checks below from the TeamTrack folder.

## Checks before you finish

- [ ] `python -m pytest tests/visible -q` passes; existing tests keep passing, unchanged.
- [ ] `lint-imports --config .importlinter` keeps both contracts (R6.5).
- [ ] A request from an Acme user with a Globex id (path or query) returns 404 `not_found` (R1.6).
- [ ] The response body has exactly `items` and `next_cursor`; `limit` above 100 is 422 (R3.2).

## Files in this skill

- `references/tests.md`: the tests a list endpoint needs, and where to copy their patterns from.

## Sources

The rules come from the TeamTrack documents this skill cites by tag: `docs/SECURITY.md` (R1, R2),
`docs/design-docs/api-conventions.md` (R3), `ARCHITECTURE.md` (R6), and
`docs/product-specs/teamtrack-base.md` (CV-06, CV-07). The skill format follows the Agent Skills
specification (https://agentskills.io/specification).
