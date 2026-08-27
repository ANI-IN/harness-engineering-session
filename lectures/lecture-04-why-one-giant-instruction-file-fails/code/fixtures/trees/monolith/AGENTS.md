# AGENTS.md

orders-service: a REST backend for order intake and reporting.

## Overview

- [overview] The service exposes JSON over HTTP and stores data in Postgres.
- [overview] Modules: api/ (routes), db/ (queries), reports/ (exports).
The sections below accumulated over months; read all of them before working.

## Style

- [style] Prefer small pure functions over classes.
- [style] Exported functions declare explicit return types.
- [style] Keep modules under 300 lines.
Notes from the style debate are kept for context; the api examples below
show the agreed formatting for api handlers.

## API rules

- [api] Every endpoint requires session auth.
- [api] Use pagination cursors, never offsets.
- [api] Error bodies follow the problem+json shape.
Some api history: the v1 api used offsets; do not copy old api examples.

## Database rules

- [security!] Every database query must be parameterized.
- [db] All schema changes ship with a migration and a rollback.
- [db] Reads go through the query helpers in db/queries.
Older db notes mention raw SQL in scripts/; those scripts are frozen.

## Testing

- [testing] Every bug fix adds a regression test first.
- [testing] Integration tests run against the docker-compose Postgres.
- [testing] Flaky tests are quarantined the same day they flake.

## Deploy

- [deploy] Releases cut from main only, tagged vX.Y.Z.
- [deploy] Run the smoke suite against staging before promoting.
- [deploy] Rollback is redeploying the previous tag, never a hotfix commit.
Deploy history and incident notes live in the wiki; summaries were pasted
here during the March incident review and never cleaned up afterwards.
