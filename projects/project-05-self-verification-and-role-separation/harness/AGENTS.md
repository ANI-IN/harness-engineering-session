# AGENTS.md, project 05 workspace

A router, not a manual: this file tells you where answers live and what
order to establish them in. Read only what the task needs.

## Startup workflow

1. Read this file (you are here).
2. Where did the last session stop: [session-handoff.md](session-handoff.md).
3. Run `bash init.sh`; fix what it names before proceeding.
4. Scope and proof obligations: `feature_list.json` (every feature
   declares its `verification` command; done means that command exits 0
   with evidence recorded). At most one feature is `in-progress` at a
   time; the doctor enforces WIP=1.
5. Session history, if the handoff is not enough:
   [claude-progress.md](claude-progress.md).

## Route by task

| Working on | Read |
| --- | --- |
| Layers, storage, exit codes | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| What the product must do | [docs/PRODUCT.md](docs/PRODUCT.md) |
| Import or the metadata index | [docs/IMPORTING.md](docs/IMPORTING.md) |
| Chunking, index state, grounded answers | [docs/INDEXING.md](docs/INDEXING.md) |
| Logs, the guard, corruption recovery | [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md) |
| Resuming or ending a session | [session-handoff.md](session-handoff.md) |
| Ending a work stream cleanly | [clean-state-checklist.md](clean-state-checklist.md) |
| What the checker grades | [evaluator-rubric.md](evaluator-rubric.md) |

## Standing rules

- When behavior surprises you, read the log first:
  `kb logs --data-dir kb-data --level WARN`. Runtime feedback beats
  re-reading source.
- The metadata index is the system of record; the chunk index is derived
  and disposable. `kb status` names `stale` and `corrupt` documents;
  `kb index --rebuild` is the recovery for corruption the sha gate
  cannot see.
- `kb ask` refuses when the index is not ready; never work around the
  refusal.
- Run `kb guard --data-dir kb-data` before calling architecture-touching
  work done; the guard executes the layer rules instead of trusting
  prose.
- Evidence is a command and its captured output; prose about the code is
  not evidence. The role that builds never grades itself:
  [evaluator-rubric.md](evaluator-rubric.md) is executed by `kb score`,
  and `kb ladder` is the standing proof that checking changes outcomes.
- Before ending a session, update [session-handoff.md](session-handoff.md)
  (canonical format: title, sections, dash-prefixed items), walk
  [clean-state-checklist.md](clean-state-checklist.md), and run
  `kb workspace-check --workspace .` until it exits 0.
