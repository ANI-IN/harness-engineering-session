# Plans

Standing plans and known debt for TeamTrack, kept in the repository so you need no outside context.
If `docs/exec-plans/active/` exists, the plan for your current feature is there; read it before you
start.

## Roadmap

| Item | Status | Where it shows up |
|---|---|---|
| Idempotency keys for issue creation | Feature 3: Safe retries for issue creation | Specified in `docs/features/f3.md` (House rule 4: Safe retries); check `app/api/issues.py` to see whether it is in place. |
| Remove the legacy /v1 API | planned | `GET /v1/issues`, `repositories.issues.list_all_legacy`, and `services.legacy` are scheduled for removal (`docs/QUALITY_SCORE.md`). |

Neither item is part of a feature ticket unless the ticket says so.

## Known debt

- The legacy /v1 API is not filtered by org, uses offset pagination, and returns a bare array. Do not
  copy it.

## How to scope a change

- Prefer small pull requests that touch only the files a feature needs.
- Feature work should not touch `app/api/middleware.py`; changes to it need a separate review.
- A schema change gets exactly one migration (House rule 7: Migrations, `docs/RELIABILITY.md`).
