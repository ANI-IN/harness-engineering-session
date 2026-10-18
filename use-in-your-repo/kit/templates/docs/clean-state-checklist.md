<!-- REPLACE: TeamTrack's definition of clean state, kept as the example: code that is ready to merge into the main branch. In TeamTrack the verify gate runs the same checks (src/shipharness/harness/verify/clean_state.py) before an agent may say done. Replace each command with your repository's and run it once before you commit this file. -->
# Clean-state checklist

Go through this list before ending a session and before saying a feature is done.

## Code

<!-- REPLACE: your test command (TeamTrack: python -m pytest tests/visible -q, run from the app folder). -->
- [ ] All tests pass: `python -m pytest tests/visible -q`. Existing tests keep passing; none were
      deleted, skipped, or changed to get there.
<!-- REPLACE: your linter, run on the Python files this change added or modified. -->
- [ ] Changed Python files are lint clean: `ruff check <changed .py files>`.
<!-- REPLACE: your migration check, or delete this item if you have no database. -->
- [ ] `alembic heads` shows exactly one `(head)`, and `alembic upgrade head` works on an empty
      database (House rule 7: Migrations).
<!-- REPLACE: the debug calls your language uses; these are the ones the gate rejects in added non-test Python lines. -->
- [ ] No debug output was added outside the tests: no `print(`, `breakpoint()`, `import pdb`, or
      `pdb.set_trace(` in the diff.
- [ ] Only files the feature needs were changed.

## App

<!-- REPLACE: your init.sh and the end-to-end check a user would make. -->
- [ ] `bash init.sh` still reaches a known state and its basic end-to-end test passes.
- [ ] The feature works end to end the way a user would use it, not only in unit tests.

## Records

- [ ] `progress.md` is updated: Done, In progress, Next.
- [ ] The exec plan's Progress and Decision Log are current.
- [ ] `session-handoff.md` has notes for the next session.
<!-- REPLACE: files your tools generate that may stay untracked (TeamTrack: caches and *.db files). -->
- [ ] Everything is committed: `git status --porcelain --untracked-files=all` prints nothing except
      generated files such as caches and `*.db` files.
