# Plans

Standing plans and known debt for TeamTrack, kept in the repository so you need no outside context.

## Roadmap

| Item | Status | Where it shows up |
|---|---|---|
| Idempotency keys for issue creation | planned | R4.6 in `docs/RELIABILITY.md` |
| Remove the legacy /v1 API | planned; waiting for the reporting client to move | CV-03 in `docs/QUALITY_SCORE.md` |

None of these items is part of a feature ticket unless the ticket says so.

## Known gaps

- The legacy /v1 API breaks R1 and R3. It stays until the reporting client moves.
- Issue creation does not accept `Idempotency-Key` (R4.6).
- `services.legacy` and `repositories.issues.list_all_legacy` exist only for the legacy endpoint.
- The demo token is not secure (CV-22); there is no real login.

## How to scope a change

- [CV-12] Prefer small pull requests that touch only the files a feature needs.

Feature work does not touch `app/api/middleware.py` (CV-02, `ARCHITECTURE.md`). A schema change gets
exactly one migration (R7.4, `docs/RELIABILITY.md`). The service is small on purpose: there is no
background worker, no cache, and no message queue; if a change seems to need one, talk to the team
first.
