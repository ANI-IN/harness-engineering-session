# Clean-state checklist

<!-- Place this file at docs/clean-state-checklist.md. [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents): "By “clean state” we mean the kind of
code that would be appropriate for merging to a main branch". Go through it before ending a session
and before saying a feature is done. Replace every <placeholder> with this repository's command. -->

## Code

- [ ] All tests pass: `<test command>`. Existing tests keep passing; none were deleted or skipped
      to get there.
- [ ] Lint and format are clean: `<lint command>`.
- [ ] Database migrations have one head, and an upgrade from an empty database works:
      `<migration check command>`.
- [ ] No debug prints, commented-out code, temporary files, or stray TODOs without an owner.
- [ ] Only files the feature needs were changed.

## App

- [ ] `./init.sh` still starts the app and the smoke test passes.
- [ ] The feature works end to end the way a user would use it, not only in unit tests.

## Records

- [ ] `progress.md` is updated (Done, In progress, Next, Session log).
- [ ] The exec plan's Progress and Decision Log are current.
- [ ] `session-handoff.md` has notes for the next session.
- [ ] Everything is committed with a descriptive message, and `git status` is clean.
