# Plans

Standing plans and known debt, kept in the repository so you need no outside context. The plan
for the current feature is in `docs/exec-plans/active/`; read it before you start.

## Roadmap

| Item | Status | Where it shows up |
|---|---|---|
| Feature 1: `peek` and `pop` docstrings name the error they raise | next | `boltons/queueutils.py`, `docs/product-specs/f1.md` |
| Make `BasePriorityQueue` a real abstract class | idea | `# TODO: make Base a real abstract class` in `boltons/queueutils.py` |
| An automated check for BQ2 (guarded imports) | idea | `ARCHITECTURE.md`; the house-rules skill scaffolds the rule, check, and test |

No item is part of a feature unless `feature_list.json` lists it.

## Known debt

- Three unused variables at `boltons/listutils.py:267` (`docs/QUALITY_SCORE.md`).

## How to scope a change

- One feature per change; touch only the files the feature needs.
- Keep each module copyable on its own (BQ2) and inside its layer (BQ1).
