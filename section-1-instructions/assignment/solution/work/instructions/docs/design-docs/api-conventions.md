# API conventions

The shape of every response and request. House rule R3 lives here, with the request-handling
conventions. Verified by the R3 check (Schemathesis plus envelope assertions).

## R3 API conventions

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
- [R3.9] The R3 check: a schema-based fuzzer (Schemathesis) plus assertions on the list and error
  envelopes.

Status codes are part of the contract: a create that returns 200, or a delete that returns a body,
fails the R3 check.

## How a list endpoint fits together

`GET /projects` (`list_projects` in `app/api/projects.py`) is the example to copy:

1. The router takes `params: PageParams = Depends(page_params)`, which reads `cursor` and `limit`.
2. It calls the service with `decode_cursor(params.cursor)` and `params.limit`.
3. The repository builds the query with `page(...)` (rows after the cursor id, ordered by id,
   `limit + 1` rows) and cuts it with `split_page(...)`, which also returns the next cursor id.
4. The router returns `to_page(rows, next_after, ProjectOut.model_validate)`, which encodes the
   cursor and builds the `Page` response model.

Why cursors and not offsets: [cursor pagination](decisions.md#2024-08-cursor-pagination).

## Error codes

| Status | Code | Raised by |
|---|---|---|
| 400 | `bad_request` | `BadRequest` |
| 400 | `invalid_cursor` | `decode_cursor` |
| 401 | `unauthorized` | `Unauthorized` (missing or invalid token, unknown email at login) |
| 403 | `forbidden` | `Forbidden` (role checks) |
| 404 | `not_found` | `NotFound` (missing, deleted, archived, or another org's resource) |
| 405 | `method_not_allowed` | the framework, wrapped in the envelope |
| 409 | `conflict` | `Conflict` (project key or email already used, member already added) |
| 409 | `idempotency_conflict` | `run_once` (R4, `docs/RELIABILITY.md`) |
| 422 | `validation_error` | request validation and `Invalid` |
| 422 | `invalid_transition` | issue status changes (`docs/product-specs/teamtrack-base.md`) |
| 422 | `invalid_assignee` | an assignee from another org (CV-25, `docs/SECURITY.md`) |
| 422 | `invalid_user` | a project member from another org (CV-25) |
| 500 | `internal_error` | any unexpected exception |

## Validation and request handling

- [CV-13] Field rules live in the services, so every caller (API, board, scripts) gets them: an
  issue title is 1 to 200 characters, a description at most 10,000 characters, and a priority one of
  low, medium, or high.
- [CV-14] Request models forbid unknown fields (`extra="forbid"`), so a body with an unknown field is
  422 `validation_error`.
- [CV-15] Path ids are bounded to what SQLite INTEGER can hold (the `Id` type in `app/api/deps.py`);
  a larger value is 422 `validation_error`, never a 500.
- [CV-16] An unexpected exception returns 500 `internal_error` in the error envelope; never leak
  internals such as tracebacks or SQL in a response.

Request and response models are in `app/api/schemas.py`. Input models end in `In`, `Create`, or
`Patch`; output models end in `Out` and are built from database rows with `model_validate`. The
validation handler reports only the first problem, as "location: message", inside the envelope.
