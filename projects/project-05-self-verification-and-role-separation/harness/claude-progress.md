# claude-progress.md, project 05 workspace

## Session 1, 2026-08-27

- Started from project 04's solution app (the starter state).
- Implemented `kb delete` end to end; decided a chunk record whose
  document left the metadata index is corrupt (the half-done delete's
  signature) and that `kb index` reconciles orphans away in both modes.
- Next best step: the maker/checker apparatus.

## Session 2, 2026-08-27

- Resumed from `session-handoff.md` alone; no oral context.
- Built workrun (one scripted work item, three flaws, three role
  configurations), score (five executable predicates, evidence re-run in
  a sandbox), and ladder (strictly climbing scores as the exit code).
- Decision: the apparatus executes canonical commands in-process, the
  project 01 precedent; the process boundary already has its proof in
  project 03.
- Verified all seventeen features with their own commands; evidence
  recorded.
- Next best step: `kb delete` drops a chunk record but leaves the log's
  `delete/done` pair unreconciled after a rebuild; reproduce with
  `kb index --rebuild` on a workspace that has deleted a document, then
  decide whether the log or the index is authoritative.
