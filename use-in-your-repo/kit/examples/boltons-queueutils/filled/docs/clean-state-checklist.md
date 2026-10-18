# Clean-state checklist

Go through this list before ending a session and before saying a feature is done.

## Code

- [ ] All tests pass: `python -m pytest --doctest-modules boltons tests -q`. Existing tests keep
      passing; none were deleted, skipped, or changed to get there.
- [ ] Changed Python files add no new lint finding: `ruff check --select F <changed .py files>`
      (the three upstream findings in `listutils.py` are known, `docs/QUALITY_SCORE.md`).
- [ ] No debug output was added outside the tests: no `print(`, `breakpoint()`, `import pdb`, or
      `pdb.set_trace(` in the diff.
- [ ] Only files the feature needs were changed.

## App

- [ ] `bash init.sh` still passes.
- [ ] The house-rule check in `AGENTS.md` prints `PASS` for `r6_layering` and `regression`.

## Records

- [ ] `progress.md` is updated: Done, In progress, Next.
- [ ] The exec plan's Progress and Decision Log are current.
- [ ] `session-handoff.md` has notes for the next session.
- [ ] Everything is committed: `git status --porcelain --untracked-files=all` prints nothing.
