# Core beliefs

The principles behind this repository's house rules, from boltons' own `docs/architecture.rst`.
Each one names the rule that carries it and the check that enforces it.

| Belief | Rule | Check |
|---|---|---|
| A module can be copied alone into another project. | BQ2 Guarded imports (`ARCHITECTURE.md`) | review |
| Dependencies between modules point one way. | BQ1 Layering (`ARCHITECTURE.md`) | `shipharness check --rules R6` |
| The package depends on no packages outside the standard library. | none yet | review |
| Every module has at least one helpful doctest, and the doctests run with the tests. | existing tests keep passing | `shipharness check --rules regression` with `--doctest-modules` |
