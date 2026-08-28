#!/usr/bin/env python3
"""Copies of a shared helper must stay identical, or say why they do not.

Curriculum code is standard-library-only and every unit is self-contained:
a lecture demo is one file a learner can read end to end and copy out. That
is a teaching property worth keeping, and it is why this repository does not
extract a shared module for the handful of helpers nine lecture demos have
in common.

The cost of that choice is drift, and drift is exactly the failure
`docs/conventions.md` cites as its own founding rationale: the reference
course's fourteen app copies diverged, one by a single character, and nine
of them stopped compiling. It had already started here. `load_workspace`
was byte-identical in two lectures and quietly different in a third, and
the TypeScript workspace type was a `Map` in two lectures and a `Record` in
a third, which forced that third lecture to hand-write a comparator the
others got for free.

So the duplication is accepted and then policed. Every copy of a registered
helper must be byte-identical to the first, unless that unit's SPEC.md
carries a line

    Helper-divergence: <name> (<reason>)

which makes the difference deliberate, reviewed, and visible in the
contract rather than discovered later by someone diffing two lectures.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Helpers several lecture demos carry verbatim. Adding a name here is a
# statement that every copy is meant to be the same code.
# `resolve_workspace` is deliberately parameterized per unit (each names the
# file that makes a directory a workspace for that lecture), so it is not
# tracked here; a helper only belongs in this registry when every copy is
# meant to be the same code.
#
# A registered name must have at least two copies, or it performs no
# comparison and the registry count overstates what the gate holds. That is
# checked below rather than trusted: `read_key` and `lines_of` were carried
# here with one copy each until the count was made to mean something.
PYTHON_HELPERS = ("load_workspace", "run_check")
TS_DECLARATIONS = ("type Files",)

DIVERGENCE = re.compile(r"^Helper-divergence:\s*(\S+)\s*\((.+)\)\s*$", re.MULTILINE)


def python_function(source: str, name: str) -> str | None:
    """The full text of a top-level `def name(...)` block, or None."""
    lines = source.split("\n")
    for index, line in enumerate(lines):
        if not line.startswith(f"def {name}("):
            continue
        body = [line]
        for following in lines[index + 1:]:
            if following and not following[0].isspace():
                break
            body.append(following)
        return "\n".join(body).rstrip() + "\n"
    return None


def ts_declaration(source: str, prefix: str) -> str | None:
    """The single line of a `type X = ...;` declaration, or None."""
    for line in source.split("\n"):
        if line.startswith(prefix):
            return line.strip()
    return None


def declared_divergences(spec: Path) -> dict[str, str]:
    if not spec.is_file():
        return {}
    return {
        match.group(1): match.group(2)
        for match in DIVERGENCE.finditer(spec.read_text(encoding="utf-8"))
    }


def check_tree(root: Path) -> tuple[list[str], dict[str, int], int]:
    """Errors, copies-per-registered-name, and comparisons actually made."""
    errors: list[str] = []
    units = sorted(root.glob("lectures/lecture-*/code"))
    registered = [*PYTHON_HELPERS, *(n.replace("type ", "") for n in TS_DECLARATIONS)]
    copies: dict[str, int] = {name: 0 for name in registered}
    comparisons = 0
    # name -> (first unit that defined it, its text)
    seen: dict[str, tuple[str, str]] = {}
    for unit in units:
        rel = unit.relative_to(root).as_posix()
        allowed = declared_divergences(unit / "SPEC.md")
        for path, names, extract in (
            (unit / "python" / "main.py", PYTHON_HELPERS, python_function),
            (unit / "typescript" / "main.ts", TS_DECLARATIONS, ts_declaration),
        ):
            if not path.is_file():
                continue
            source = path.read_text(encoding="utf-8")
            for name in names:
                text = extract(source, name)
                if text is None:
                    continue
                key = name if name in PYTHON_HELPERS else name.replace("type ", "")
                copies[key] += 1
                if key not in seen:
                    seen[key] = (rel, text)
                    continue
                origin, expected = seen[key]
                comparisons += 1
                if text == expected or key in allowed:
                    continue
                errors.append(
                    f"{path.relative_to(root).as_posix()}: `{key}` differs from the "
                    f"copy in {origin}; make them identical or declare "
                    f"`Helper-divergence: {key} (<reason>)` in {rel}/SPEC.md"
                )
    for name, count in sorted(copies.items()):
        if count < 2:
            errors.append(
                f"registry: `{name}` has {count} copy(ies) across lecture demos, so "
                f"it is compared against nothing; remove it from the registry or "
                f"register a name that several demos actually share"
            )
    return errors, copies, comparisons


def main() -> int:
    errors, copies, comparisons = check_tree(REPO_ROOT)
    print(
        f"lint-shared-helpers: {len(copies)} registered helper(s), "
        f"{sum(copies.values())} copy(ies), {comparisons} byte-identity "
        f"comparison(s) across lecture demos"
    )
    for error in errors:
        print(f"  FAIL {error}")
    if errors:
        print(f"lint-shared-helpers: {len(errors)} error(s)")
        return 1
    print("lint-shared-helpers: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
