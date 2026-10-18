# Module 1: Harness Engineering for Coding Agents - Worked example: the kit on boltons

## The problem

**Illustrative scenario.** You copy a harness template into your repository and start filling it
in. Halfway through, you are unsure what a finished file should look like for code that is not a
multi-tenant web app. Should the security document stay? What does a house rule look like for a
library? Without a filled example, you guess.

> **Terms on this page**
>
> - **Kit**: TeamTrack's harness as templates, copied into your repository by `shipharness init`.
> - **REPLACE marker**: a line in a kit template that says what to write in place of the example value.
> - **House rule**: a team convention written as one checkable sentence, with a check that finds violations.

This folder is that filled example. It is the end state of the worked example in
[apply-to-your-repo.md](../../../apply-to-your-repo.md): the kit installed with `shipharness init`
and filled in for a small real repository. The repository is three modules of boltons 26.2.0
(`typeutils`, `listutils`, `queueutils`) with their tests. boltons is BSD-3-Clause. The course
already pins it for `shipharness testgen` (`platform/datasets/sources/testgen.toml`), and
`platform/scripts/fetch_testgen_libs.py` fetches it without a model call.

## Rebuild the starting repository

```bash
uv run python platform/scripts/fetch_testgen_libs.py boltons
bash use-in-your-repo/kit/examples/boltons-queueutils/make_repo.sh /tmp/bq-example
```

`make_repo.sh` copies the three modules, their tests, `LICENSE`, and `.gitignore` from the pinned
clone into a new git repository and commits them. The boltons code is not stored in this folder.
It stops with `ERROR boltons clone not found at ...` when the fetch has not run, and with
`ERROR <dir> already exists: pick a new directory` when the target folder is taken; run the fetch, or pick a new folder.

## What is in `filled/`

Every kit file as it reads after filling, in the same layout as the repository. Compare a file here
with the same path in [`use-in-your-repo/kit/templates/`](../../templates/) to see what changed.

| Decision | Files |
|---|---|
| Rewritten for this repository | `AGENTS.md`, `ARCHITECTURE.md`, `docs/QUALITY_SCORE.md`, `docs/PLANS.md`, `docs/design-docs/`, `docs/product-specs/`, `docs/references/import-linter-llms.txt`, `docs/clean-state-checklist.md`, `docs/house-rules.md`, the state files, `feature_list.json`, `init.sh`, `harness/`, `.github/workflows/shipharness.yml` |
| Kept as copied, marker lines removed | `feature_list.schema.json`, `harness/sandbox-policy.toml` |
| Deleted: they do not apply to a library with no API, tenants, or database | `docs/SECURITY.md`, `docs/RELIABILITY.md`, `docs/design-docs/api-conventions.md`, `docs/design-docs/cursor-pagination.md`, `docs/product-specs/teamtrack-base.md`, `docs/references/alembic-llms.txt` |
| Added | `docs/product-specs/queueutils.md` (replaces `teamtrack-base.md`), `harness/check-baseline.json` (written by `shipharness check --json`) |

The feature in `feature_list.json` is real: the docstrings of `peek` and `pop` say an empty queue
raises `KeyError`, and the code raises `IndexError` (`docs/product-specs/f1.md` in `filled/`).

`platform/tests/unit/kit/test_example.py` keeps this folder honest: no REPLACE marker is left, the files
kept as copied still match the kit, and, when the boltons clone is present, the house-rule check
passes on a rebuilt repository.
