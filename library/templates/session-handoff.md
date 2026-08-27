<!--
  Template: session-handoff.md, the compact note one session leaves the next.
  Use when: sessions end mid-task, or a different agent/person picks up next.
  Don't use when: the task finished cleanly; claude-progress.md already
  carries the record; a handoff of "nothing in flight" is noise.
  Motivated by: Lecture 05 (Why long-running tasks lose continuity).
  Kept deliberately short: a handoff nobody reads is a handoff that failed.
-->

# Session handoff

## Verified now

- `./verify.sh note-create`: exit 0
- Build and full test suite green at commit `3f2a91c`

## Changed this session

- `src/list.py` / `src/list.ts`: listing implemented, output format final.
- `feature_list.json`: `note-list` set to `in-progress`.

## Broken or unverified

- `note-list` sort order: assertion fails; dates compare as strings but
  fixtures contain mixed formats. Not a flake; reproduce with
  `./verify.sh note-list`.

## Next best step

Normalize dates to ISO 8601 at write time (see Session 002 decision in
`claude-progress.md`), then re-run `./verify.sh note-list`.

## Commands

- Start: `./init.sh`
- Verify everything: `./verify.sh`
- Reproduce the open failure: `./verify.sh note-list`
