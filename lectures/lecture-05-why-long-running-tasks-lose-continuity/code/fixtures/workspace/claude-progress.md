# Progress

## Current verified state

- Commit: `4e5f6a7`
- Verification: `./verify.sh`: exit 0 for import-notes (2026-08-26)
- Next best step: finish format-dates using the recorded reproduce command

## Session log

### Session 001 (2026-08-26)

- Goal: format-dates.
- Done: renderer written; half the assertions pass.
- Decisions: dates are stored as ISO 8601 strings, never file mtimes.
- Next: fix the sort assertion, then archive-notes.
