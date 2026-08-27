# AGENTS.md

pay-service: payment intake and reconciliation.

## Hard constraints

- [security!] Card numbers never appear in logs or errors.

## Topic docs

- docs/api.md for endpoint work
- docs/db.md for schema and query work
- docs/deploy.md for releases

- [api] Use pagination cursors, never offsets.
