"""Filter and referee sets stay disjoint across every TeamTrack mutant file.

A module file (`platform/teamtrack/mutants/<module>.jsonl`) and a feature file
(`platform/teamtrack/mutants/features/<task>.jsonl`) can mutate the same line. If one file puts a
mutation in the filter set and another puts the same mutation in the referee set, a test written
to kill the filter mutant also kills the referee mutant, and the referee no longer measures
held-out behaviour.
`overlaps` reports every such pair, and every id used twice.

A mutation is identified by (file, original, replacement) after whitespace normalisation. Mutations
that are written differently but behave the same are not machine-detectable; the pairs found by
review and how each was resolved are recorded below.

Reviewed equivalent pairs (each resolved by replacing the filter-side record, since
filter sets never judge an arm):

- `app.services.context-m1` (filter: viewer in WRITER_ROLES) behaved like the referee mutants that
  make `can_write` return True (`app.services.context-m4`, `features/f4`
  `app.services.context-m401`, `features/f7` `app.services.context-m701`). Replaced: admins lose
  write access.
- `app.services.context-m3` (filter: `is_admin` is `role != "viewer"`) behaved like
  `features/f2` `app.services.context-m201` and `features/f6` `app.services.context-m601`
  (referee: `role in ("admin", "member")`). Replaced: nobody is an admin.
- `app.services.idempotency-m1` and `features/f3` `app.services.idempotency-m304` (filter: a
  constant request hash) behaved like the referee `if False:` on the conflict check
  (`features/f2` m201, `features/f3` m302, `features/f7` m701). Replaced: the first keyed create
  answers 200 (module), keyed creates are flushed but not committed, and the stored response body
  is empty (F3).
- `app.services.audit-m1` (filter: `return None`) behaved like `features/f7`
  `app.services.audit-m701` (referee: `pass`). Replaced: action and entity are swapped.
- `app.repositories.idempotency-m4` (referee: store status 200) behaved like `features/f7`
  `app.services.idempotency-m702` (filter: replay status 200), which was also an exact copy of
  `features/f3` `app.services.idempotency-m303` (referee). Replaced the F7 filter record.
- `features/f7` `app.api.deps-m701` (filter: `require_writer` never refuses) behaved like
  `features/f7` `app.services.context-m701` (referee: `can_write` is True) for every API write. The
  same filter mutation in `features/f2`, `f5`, and `f6` (`app.api.deps-m201`, `-m501`, `-m601`) had
  the same twin in the referee sets of other files. All four replaced.
- Exact cross-file copies found by review and now caught by `overlaps`: `common.py` `>=`
  (`app.repositories.common-m2` referee, `features/f1` m101 filter), `projects.py` without the org
  filter (`app.repositories.projects-m1` filter, `features/f1` m102 referee), `idempotency.py`
  `if True:` (`app.services.idempotency-m2` referee, `features/f3` m305 filter), `audit.py` `pass`
  (`features/f2`, `f5`, `f6` filter, `features/f7` referee), `idempotency.py` `return 200`
  (`features/f3` m303 referee, `features/f7` m702 filter). Each filter-side record was replaced.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from shipharness.config.prices import REPO_ROOT
from shipharness.layout import APP_DIR

MUTANTS_DIR = REPO_ROOT / APP_DIR / "mutants"


def mutant_files(root: Path = MUTANTS_DIR) -> list[Path]:
    """Every TeamTrack mutant file: the module files and the feature files under `features/`."""
    return sorted(Path(root).rglob("*.jsonl"))


def _norm(text: str) -> str:
    return " ".join(text.split())


def overlaps(paths: Iterable[Path] | None = None) -> list[str]:
    """Problems across the given mutant files (default: all TeamTrack mutant files): a mutation
    present in both the filter and the referee set, and an id used more than once."""
    from shipharness.filters.mutants import load_mutants

    by_change: dict[tuple[str, str, str], dict[str, list[str]]] = defaultdict(
        lambda: {"filter": [], "referee": []}
    )
    where_id: dict[str, list[str]] = defaultdict(list)
    for path in mutant_files() if paths is None else [Path(p) for p in paths]:
        for m in load_mutants(path, None):
            label = f"{m.id} ({path.parent.name}/{path.name})"
            where_id[m.id].append(label)
            key = (m.file, _norm(m.original), _norm(m.replacement))
            by_change[key][m.set].append(label)
    problems = [
        f"{file}: the same mutation is in the filter set ({', '.join(sets['filter'])}) and the "
        f"referee set ({', '.join(sets['referee'])}): {original!r} -> {replacement!r}"
        for (file, original, replacement), sets in sorted(by_change.items())
        if sets["filter"] and sets["referee"]
    ]
    problems += [
        f"duplicate id {mid}: {', '.join(labels)}"
        for mid, labels in sorted(where_id.items())
        if len(labels) > 1
    ]
    return problems
