# AGENTS.md, project 01 workspace

Rules for any agent working in this directory. The task prompt is vague on
purpose; this file is what makes it concrete.

## Startup workflow

Complete these steps in order before writing any code:

1. Read this file completely.
2. Read `docs/ARCHITECTURE.md` for the layer rules and `docs/PRODUCT.md`
   for what the product must do.
3. Run `bash init.sh`. If it fails, fix what it names before proceeding.
4. Read `feature_list.json`. It is the entire scope: nothing outside it,
   nothing in it skipped.
5. Read `claude-progress.md` to see what earlier sessions did.

## Scope and verification

- `feature_list.json` declares every feature with a `verification` command.
  A feature is done when that exact command exits 0 and its output is
  recorded in the feature's `evidence` (command, observed, date).
- Run the verification command yourself. Prose about the code is not
  evidence; only a command and its captured output are.
- Work features in list order; each later feature depends on the data
  directory existing.

## Layer rules

- Storage is plain files under the data directory; no database.
- The HTTP server binds loopback only and reuses the same functions as the
  CLI; no logic lives only in the server.
- The answer composer is deterministic; a model call may replace it later
  but must preserve the citation contract.

## Definition of done

All features in `feature_list.json` at status `passing`, each with
evidence; `claude-progress.md` updated with what happened and the next
best step. Declaring done with an unverified feature is the failure mode
this whole harness exists to prevent.
