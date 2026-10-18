# AGENTS.md

This file is the map of this repository: a table of contents, not the manual. It tells you where
each rule lives. Open the document for the part you are changing before you edit code.

Three utility modules from boltons 26.2.0 (BSD-3-Clause, `LICENSE`): `typeutils`, `listutils`, and
`queueutils`. Each module must keep working when someone copies it alone into another project, with
the standard library only.

## Where to look

| When you are about to | Read first |
|---|---|
| import one module from another | `ARCHITECTURE.md` (layers, BQ1 and BQ2) |
| change how a queue behaves (`add`, `remove`, `peek`, `pop`) | `docs/product-specs/queueutils.md` |
| work on a feature from `feature_list.json` | its spec in `docs/product-specs/` and its plan in `docs/exec-plans/active/` |
| write or run tests | `docs/QUALITY_SCORE.md` (testing, known gaps) |
| plan a change or check the roadmap | `docs/PLANS.md` |
| understand why the code is shaped this way | `docs/design-docs/core-beliefs.md` |
| read what the layering check prints | `docs/references/import-linter-llms.txt` |
| decide which house rules apply here | `docs/house-rules.md` |

## House rules at a glance

- BQ1 Layering: `queueutils` may import `listutils` and `typeutils`; `listutils` may import
  `typeutils`; `typeutils` imports no other module here. Checked by `shipharness check --rules R6`.
- BQ2 Guarded imports: an import of another module here sits in `try: ... except ImportError:` with
  a fallback, so a module copied alone still imports. Checked in review (no automated check yet).
- Existing tests keep passing, doctests included. Checked by `shipharness check --rules regression`.

## Commands

Run these from the repository root, in an environment with Python 3.12 and pytest.

| Task | Command |
|---|---|
| start-of-session check | `bash init.sh` |
| run every test, doctests included | `python -m pytest --doctest-modules boltons tests -q` |
| lint the files you changed | `ruff check --select F <changed .py files>` |
| check BQ1 and the existing tests | `PYTHONPATH=harness uv run --project ~/shipharness shipharness check --app . --adapter shipharness_adapter:HouseRulesAdapter --rules R6,regression --params harness/check-params.json` |

## Repository layout

```
boltons/     typeutils.py, listutils.py, queueutils.py, and __init__.py (the version)
tests/       one test file per module; conftest.py skips files named for other Python versions
harness/     the house-rule adapter, its params and baseline, the sandbox policy
docs/        the system of record (this map points into it)
```

## Before you finish

- `python -m pytest --doctest-modules boltons tests -q` passes, and existing tests keep passing,
  unchanged.
- The shipharness check command above prints `PASS` for `r6_layering` and `regression`.
- `docs/clean-state-checklist.md` is done.

## Start of every session

1. Run `pwd` to see the directory you are working in. You can only edit files in this directory.
2. Read progress.md and the git log (`git log --oneline -20`) to see what was recently worked on.
3. Read session-handoff.md (the structured handoff from the last session) and the exec plan docs/exec-plans/active/F1.md.
4. Read the "Notes from the agent" in session-handoff.md before any other document. Open a document from this map only for a detail the notes do not cover.
5. Read feature_list.json and work on the feature listed there, and only it.
6. Run `bash init.sh` to check the modules import and run a basic end-to-end test.
7. If init.sh fails, fix that before you start new work.

## End of every session

1. Update progress.md: Done, In progress, and Next.
2. Update the exec plan docs/exec-plans/active/F1.md: Progress (with timestamps) and Decision Log.
3. Write your notes under "## Notes from the agent" in session-handoff.md: what you were doing, what is left, what to watch out for.
4. Commit your work to git with a descriptive message (git add, then git commit).
