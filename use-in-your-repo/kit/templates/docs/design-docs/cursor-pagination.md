<!-- REPLACE: an example design decision with its reason. Write your own, or delete this file and its row in index.md. -->
# Cursor pagination

Status: in force. Verified by the check for House rule 3: API conventions.

## Decision

Lists use keyset pagination by ascending id with an opaque cursor. They return
`{"items": [...], "next_cursor": "..." | null}`, accept `cursor` and `limit` (1 to 100, default 20),
and set `next_cursor` null on the last page. Do not use offset pagination. The helpers are in
`app/api/pagination.py`.

## Why

We moved from offset to cursor pagination after a customer reported missing rows while paging
through a busy project.

## What is left

`GET /v1/issues` still uses offset pagination. It is a legacy endpoint scheduled for removal; do not
copy it (`docs/QUALITY_SCORE.md`).
