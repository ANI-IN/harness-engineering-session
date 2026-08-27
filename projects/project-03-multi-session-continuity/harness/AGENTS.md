# AGENTS.md, project 03 working copy

A router, not a manual: this file tells you where answers live and what
order to establish them in. Read only what the task needs.

## Startup workflow

1. Read this file (you are here).
2. Where did the last session stop: [session-handoff.md](session-handoff.md).
3. Run `bash init.sh`; fix what it names before proceeding.
4. Scope and proof obligations: `feature_list.json` (every feature
   declares its `verification` command; done means that command exits 0
   with evidence recorded).
5. Session history, if the handoff is not enough:
   [claude-progress.md](claude-progress.md).

## Route by task

| Working on | Read |
| --- | --- |
| Layers, storage, exit codes | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| What the product must do | [docs/PRODUCT.md](docs/PRODUCT.md) |
| Import or the metadata index | [docs/IMPORTING.md](docs/IMPORTING.md) |
| Chunking, index state, grounded answers | [docs/INDEXING.md](docs/INDEXING.md) |
| Resuming or ending a session | [session-handoff.md](session-handoff.md) |
| Ending a work stream cleanly | [clean-state-checklist.md](clean-state-checklist.md) |

## Standing rules

- The metadata index is the system of record; listing never rescans the
  documents directory. The chunk index is derived state; `kb status` says
  whether it is current.
- `kb ask` refuses when the index is not ready; never work around the
  refusal by answering from unindexed text.
- Evidence is a command and its captured output; prose about the code is
  not evidence.
- Before ending a session, update [session-handoff.md](session-handoff.md)
  (canonical format: title, sections, dash-prefixed items), walk
  [clean-state-checklist.md](clean-state-checklist.md), and run
  `kb workspace-check --workspace .` until it exits 0.
