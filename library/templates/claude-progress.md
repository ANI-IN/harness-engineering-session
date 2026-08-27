<!--
  Template: claude-progress.md — cross-session progress log.
  Use when: work spans more than one agent session.
  Don't use when: genuinely single-session tasks — the git log is enough.
  Motivated by: Lecture 05 (Why long-running tasks lose continuity).
  Rules: the "Current verified state" block is overwritten each session;
  the session log is append-only. Agents read this file first and update it
  last — say so in AGENTS.md, or it will be ignored.
-->

# Progress

## Current verified state

- Commit: `3f2a91c`
- Verification: `./verify.sh` — exit 0 (2026-08-27)
- Features passing: 1 / 3 (`note-create`)
- Known broken: nothing
- Next best step: finish `note-list` date sorting, then run `./verify.sh note-list`

## Session log

### Session 002 — 2026-08-27

- Goal: implement `note-list`.
- Done: listing works; output format matches SPEC.
- Not done: sort by modified date (started, not verified).
- Verification run: `./verify.sh note-list` — exit 1 (sort order assertion).
- Decisions: store dates as ISO strings in front matter, not file mtimes —
  mtimes don't survive `git clone`.
- Next: implement the sort, re-run verification, update feature_list.json.

### Session 001 — 2026-08-26

- Goal: project setup + `note-create`.
- Done: `init.sh` green on fresh clone; `note-create` passing with evidence.
- Verification run: `./verify.sh` — exit 0.
- Decisions: notes stored as one markdown file each under `data/notes/`;
  no database — files are the state.
- Next: `note-list`.
