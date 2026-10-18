# Exec plan for {{feature}}

This execution plan is a living document checked into the repository. Keep it self-contained:
a new session must be able to restart from this plan, progress.md, and the git log alone. The
harness moves it to docs/exec-plans/completed/ when the feature passes.

## Purpose

{{description}}

Steps from the ticket:

{{steps}}

## Progress

- [x] Harness initializer step: init.sh, progress.md, session-handoff.md, and this plan created.
- [ ] (add one line per step with a UTC timestamp, for example 2026-10-16T10:00Z)

## Surprises & Discoveries

- None yet.

## Decision Log

- None yet. Record each decision with the reason and the date.

## Outcomes & Retrospective

- Not finished yet.

## Validation

- `bash init.sh` (migrations at one head, basic test run)
- `python -m pytest tests/visible -q`
