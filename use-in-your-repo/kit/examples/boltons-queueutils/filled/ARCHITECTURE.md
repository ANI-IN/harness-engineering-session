# Architecture

A top-level map of this repository's modules and how they may depend on each other.

## Domains

Three modules copied from boltons 26.2.0 (commit 4332b35, BSD-3-Clause). boltons describes its
design in its own `docs/architecture.rst`: "The ``boltons`` package depends on no packages", and
modules are "as self-contained as possible, allowing cherrypicking of functionality into projects".

| Module | What it holds | Tests |
|---|---|---|
| `boltons/typeutils.py` | `make_sentinel`, `issubclass`, `get_all_subclasses`, `classproperty` | `tests/test_typeutils.py`, 3 doctests |
| `boltons/listutils.py` | `BarrelList` (also exported as `BList`) and `SplayList` | `tests/test_listutils.py`, 1 doctest |
| `boltons/queueutils.py` | `BasePriorityQueue`, `HeapPriorityQueue`, `SortedPriorityQueue` (`PriorityQueue`) | `tests/test_queueutils.py`, 1 doctest |

## Layers

| Layer | Module | May import |
|---|---|---|
| top | `boltons.queueutils` | `listutils`, `typeutils`, the standard library |
| middle | `boltons.listutils` | `typeutils`, the standard library |
| bottom | `boltons.typeutils` | the standard library only |

## BQ1 Layering

A module imports only modules below it in the table above.

The check: `shipharness check --rules R6` runs an import-linter layers contract that lives in
`harness/shipharness_adapter.py`, not in this repository's own configuration. The command is in
`AGENTS.md`; what its output means is in `docs/references/import-linter-llms.txt`.

## BQ2 Guarded imports

An import of another module here sits in `try: ... except ImportError:` with a fallback, so a
module copied alone still imports. `queueutils` shows the pattern: without `listutils`, `BList`
falls back to `list`; without `typeutils`, the `_REMOVED` sentinel falls back to `object()`.

The check: review only. A file that imports another module here without the guard is a review
finding until an automated check exists (`docs/PLANS.md`).
