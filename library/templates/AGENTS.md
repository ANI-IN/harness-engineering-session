<!--
  Template: AGENTS.md, the agent-facing entry point and working contract.
  Use when: any repository where a coding agent does multi-step work.
  Don't use when: a one-shot script with no repo state to protect.
  Motivated by: Lecture 02 (What a harness actually is) and Lecture 04
  (Why one giant instruction file fails).
  How to adopt: replace the example project facts below with yours; keep the
  section structure and the startup/end-of-session workflows intact.
-->

# AGENTS.md

You are working in **example-notes-app**, a CLI tool that stores markdown
notes locally and answers questions about them. Local files only; no network
at runtime.

Keep this file short. It is a router: project facts live in the linked docs,
not here.

## Startup workflow

Run these steps at the start of every session, in order:

1. `./init.sh`: installs dependencies and verifies the environment.
2. Read `claude-progress.md`: the current verified state and last session's notes.
3. Read `feature_list.json`: pick the single highest-priority feature that is
   `not-started`, or resume the one `in-progress`.
4. Run the verification command for the current state before changing anything.

## Working rules

- **WIP=1.** At most one feature `in-progress` at any time.
- Only touch files needed for the current feature. Anything else is overreach.
- A feature becomes `passing` only via its verification command; record the
  command and result in its `evidence` field.
- If blocked, set the feature's status to `blocked` with a note; do not start
  a different feature to feel productive.
- Never delete or rewrite `claude-progress.md` history; append.

## Verification commands

- Full check: `./verify.sh`
- Tests only: `uv run pytest` (Python) / `pnpm test` (TypeScript)

## Definition of done

A feature is done when all of the following hold:

- [ ] Its verification command exits 0.
- [ ] Its `feature_list.json` entry is `passing` with evidence recorded.
- [ ] No other feature's verification broke.
- [ ] New behavior is reachable from the app's entry point, not just from tests.

## End of session

1. Run the full verification command; fix or record any failure.
2. Update `feature_list.json` statuses and evidence.
3. Append a session entry to `claude-progress.md`.
4. Leave no stray files (scratch scripts, debug output, temp data).
5. State the next best step in your final message and in the progress file.
