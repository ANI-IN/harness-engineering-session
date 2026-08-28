<!--
  Template: evaluator-rubric.md, the checker's scorecard over a maker's work.
  Use when: a separate checker role (agent or human) reviews a session's
  output; the maker never fills in its own rubric.
  Don't use when: trivial changes fully covered by automated checks; the
  rubric adds judgment where automation ends, not paperwork where it doesn't.
  Motivated by: Lecture 08 (Why agents declare victory too early): makers are
  systematically overconfident; the verdict must come from outside.
  Tuning note: out of the box, agent checkers drift lenient: they identify
  issues and then talk themselves into approving. Expect several tuning
  rounds; tighten the questions until scores track outcomes you observe.
-->

# Evaluator rubric

- Work under review: Session 002, `note-list` implementation
- Maker: implementation agent · Checker: this rubric's author (separate role)
- Date: 2026-08-27

Score each category 0 (fails), 1 (partial), 2 (meets). Cite evidence: a
command run, a file read, an output seen. A score without evidence is invalid.

| Category | Question | Score | Evidence |
| --- | --- | --- | --- |
| Correctness | Does the claimed behavior work end to end, run fresh? | 1 | `./verify.sh note-list` exit 1: sort assertion fails |
| Verification | Was every status claim backed by an executed command? | 2 | evidence fields in `feature_list.json` reference real runs |
| Scope | Did the work stay inside the declared feature (WIP=1)? | 2 | diff touches `list.*` only |
| State | Are progress and feature files updated and truthful? | 2 | `claude-progress.md` Session 002 matches the diff |
| Clean state | Would the clean-state checklist pass right now? | 1 | one scratch file `notes-debug.txt` left in repo root |
| Handoff | Could a fresh session resume from the written handoff alone? | 2 | handoff names failure + reproduce command |

Total score: **10 / 12**

## Verdict

**Revise** (Accept / Revise / Block). Listing is real and scoped, but the
open sort failure and the stray debug file must be resolved or explicitly
carried in the handoff before this session's work is accepted.

## Required follow-up

1. Delete `notes-debug.txt`.
2. Fix date normalization; re-run `./verify.sh note-list` until exit 0.
3. Update `note-list` to `passing` with the new evidence.
