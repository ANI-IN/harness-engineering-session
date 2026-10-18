# Decisions and history

Why the rules are what they are. Dated, newest at the bottom. Nothing here is a rule: each rule is
defined once, in the document `AGENTS.md` points to, and cited here by its tag.

## 2024-05 Layering checked by a tool

A router imported a model directly and skipped the org filter. The fix took ten minutes; finding the
leak took a week. The layering rule and import-linter came out of it (R6, `ARCHITECTURE.md`).

## 2024-06 Another org's resource is 404

One endpoint answered 403 for another org's issue and 404 for a missing one. A customer's script
walked the ids from 1 upwards and printed every issue id that existed in other orgs. The handler had
loaded the issue by id alone and compared `org_id` afterwards. Now every repository function takes
`org_id` and filters on it, and the service raises `NotFound` when the scoped query finds nothing
(R1.1, R1.2, R1.3 in `docs/SECURITY.md`).

## 2024-08 Cursor pagination

We moved from offset to cursor pagination after a customer reported missing rows while paging
through a busy project: rows inserted during paging shifted the offsets. Cursors page by ascending
id, so new rows never shift a page (R3.2, R3.3).

## 2024-09 Deletes return 204

A client had parsed the old 200 body of a delete and broke when it changed; one rule for every
delete was judged worth one broken client (R3.6). The old convention, CV-23, is retired.

## 2024-11 Archiving is admin-only

A member archived the wrong project and nobody could find out who did it. Archiving became
admin-only (R2.2) and gained an audit entry. The old rule that let members archive, R2.5, is retired.

## 2025-01 One migration head

A second Alembic head appeared after two people added migrations on the same day; both created the
same column. Run `alembic heads` first and edit an unreleased migration instead of adding another
(R7.3, R7.4). Creating development databases from the models, R7.5, is retired; only the tests use
`TEAMTRACK_CREATE_SCHEMA`.

## 2025-03 Rule tags

Rule tags were added. Offset pagination for admin exports, R3.8, was retired at the same time.

## 2025-04 Idempotency keys

A mobile client retried a timed-out `POST /projects` and created two projects. Keys are scoped per
org and per endpoint so that two orgs can use the same key value (R4.4).

## 2025-06 Replays add no audit row

The audit log double-counted idempotent replays for a week, because the replay path called the
service again. `run_once` now returns the stored response without running the create (R5.3).

## 2025-10 The legacy handler gets copied

An agent working a feature ticket copied the legacy /v1 handler because it was the shortest example
of "list issues". That is why the map and `docs/QUALITY_SCORE.md` say "do not copy" (CV-03).

## 2026-01 Corrections are new rows

A request to add "delete audit entry" was turned down; the audit log is append-only (R5.5).

## 2026-04 Splitting the instruction file

The single instruction file had grown past 800 lines, agents read all of it for every task, and
review comments cited retired rules. It was split into this map and these documents, with a checker
that fails on a broken link or on a tagged rule that is missing from the new documents.

## Review comments we reuse

- "This query has no `org_id` filter." (R1.1)
- "Another org's resource must look missing: raise `NotFound`, not `Forbidden`." (R1.2, R1.3)
- "The assignee id comes from the body; check it belongs to the caller's org." (R1.4)
- "Writes need `require_writer` (or `require_admin` for user, member, and archive changes)." (R2.3)
- "Lists return `items` and `next_cursor`; please use `page_params` and `to_page`." (R3.1, R3.2)
- "This create needs `Idempotency-Key` through `run_once`." (R4.1, R4.5)
- "This write has no audit row." (R5.1)
- "Routers do not import models; add a service function." (R6.4)
- "There are two migration heads now; rebase your migration on the current head." (R7.2, R7.3)
- "Please do not start from the /v1 handler." (CV-03)
- "Please add tests for the other org and for the viewer." (CV-09)
