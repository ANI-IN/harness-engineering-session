# Quality score

Grades for each module and the gaps we track. Update a row when a change closes or opens a gap.

Grades: **meets rules** (no gap recorded), **gap** (a known shortfall that is on the roadmap).

## Modules

| Module | Grade | Notes |
|---|---|---|
| `typeutils` | meets rules | Imports the standard library only (bottom layer, BQ1). |
| `listutils` | gap | `ruff check --select F` reports three unused variables (`start`, `stop`, `step`) at `listutils.py:267`, upstream code. |
| `queueutils` | gap | The docstrings of `peek` and `pop` say an empty queue raises `KeyError`; the code raises `IndexError`. Feature 1. |

## Testing

- Tests live in `tests/`, one file per module. Doctests in the modules are part of the suite.
- `python -m pytest --doctest-modules boltons tests -q` runs 21 tests: 16 test functions and 5
  doctests.
- For any behaviour you change, add a test in the module's test file, and keep the module's doctest
  working.
- Do not change existing tests to make a change pass.
