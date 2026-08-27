# claude-progress.md, project 04 workspace

## Session 1, 2026-08-27

- Started from project 03's solution app (the starter state).
- Implemented structured logging (sequence-numbered events, no wall
  clock, per the course determinism rule) and the `kb logs` surface.
- Decision: read surfaces never write the log; `ask` does, because
  retrieval quality and refusals are the runtime feedback this project
  exists to expose.
- Next best step: corruption detection and the recovery path.

## Session 2, 2026-08-27

- Resumed from `session-handoff.md` alone; no oral context.
- `kb status` now detects empty-chunk corruption the sha gate cannot see
  and names the documents; `kb index --rebuild` recovers; a refused
  `kb ask` logs the state at WARN.
- Implemented `kb guard` (server read-only, storage containment,
  disposable derived state) and the 405 write refusal; added the WIP=1
  check to the workspace doctor.
- Verified all fifteen features with their own commands; evidence
  recorded.
- Next best step: proceed to Project 05 (self-verification and role
  separation) when it lands.
