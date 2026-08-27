#!/usr/bin/env python3
"""Structure checker.

Enforces the repository conventions that rot silently if unchecked
(docs/conventions.md is the human-readable statement of the same rules):

1. Every curriculum directory that must carry a README.md has one.
2. Every conformance unit (SPEC.md) is complete: fixtures/, expected/,
   both stacks present (python/typescript or starter+solution variants),
   and cases.json. Conversely, unit parts without a SPEC.md (a stray
   cases.json, or fixtures/ + expected/ with no contract) are errors.
3. Every exercise directory is complete: README.md, SPEC.md, verify.sh,
   starter/{python,typescript}, solution/{python,typescript}.
4. Lecture and project READMEs follow the required H2 section order.
5. No orphan directories (dirs with no files anywhere below).
6. Fail on empty: discovered lecture/project/exercise counts must meet the
   floors in tools/expected_counts.json, so a broken glob fails loudly.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COUNTS_MANIFEST = REPO_ROOT / "tools" / "expected_counts.json"
UNIT_ROOTS = ("lectures", "projects", "tools/conformance/selftest")
SKIP_DIRS = {
    "node_modules", "_reference", ".git", ".venv",
    "__pycache__", "dist", ".pytest_cache", ".ruff_cache",
}

LECTURE_SECTIONS = [
    "Learning objectives",
    "Prerequisites",
    "The problem",
    "Concepts",
    "Architecture",
    "Demo",
    "Implementation notes",
    "Key takeaways",
    "Exercises",
    "Further exploration",
]

PROJECT_SECTIONS = [
    "Overview",
    "Learning objectives",
    "Prerequisites",
    "Architecture",
    "Project structure",
    "Setup",
    "Usage",
    "Demo flow",
    "Testing and validation",
    "Expected output",
    "Troubleshooting",
    "Extension challenges",
    "Related lectures",
]

EXERCISE_SECTIONS = [
    "Objective",
    "Why this matters",
    "Prerequisites",
    "Provided",
    "Your task",
    "Expected outcome",
    "How to verify",
    "Hints",
    "Solution walkthrough",
]


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)


def _iter_dirs(base: Path):
    for path in sorted(base.rglob("*")):
        if path.is_dir() and not any(part in SKIP_DIRS for part in path.parts):
            yield path


def _headings(md: Path) -> list[str]:
    text = md.read_text(encoding="utf-8")
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return [m.group(1).strip() for m in re.finditer(r"^##\s+(.*)$", text, re.MULTILINE)]


def _check_section_order(md: Path, required: list[str], errors: list[str], root: Path) -> None:
    present = _headings(md)
    positions = []
    for section in required:
        matches = [i for i, h in enumerate(present) if h.lower().startswith(section.lower())]
        if not matches:
            errors.append(f"{_rel(md, root)}: missing section '## {section}'")
        else:
            positions.append((section, matches[0]))
    ordered = [p for _, p in positions]
    if ordered != sorted(ordered):
        errors.append(f"{_rel(md, root)}: sections out of required order")


def check_readmes(errors: list[str], root: Path) -> None:
    needs_readme = []
    for top in ("lectures", "projects", "skills", "library", "tools"):
        base = root / top
        if not base.is_dir():
            continue
        needs_readme.append(base)
        for child in sorted(base.iterdir()):
            if child.is_dir() and child.name not in SKIP_DIRS:
                needs_readme.append(child)
    for directory in needs_readme:
        if not (directory / "README.md").is_file():
            errors.append(f"{_rel(directory, root)}: missing README.md")


def check_units(errors: list[str], root: Path) -> None:
    for top in UNIT_ROOTS:
        base = root / top
        if not base.is_dir():
            continue
        for spec in sorted(base.rglob("SPEC.md")):
            unit = spec.parent
            rel = _rel(unit, root)
            for required in ("fixtures", "expected"):
                if not (unit / required).is_dir():
                    errors.append(f"{rel}: SPEC.md unit missing {required}/")
            plain = (unit / "python").is_dir() and (unit / "typescript").is_dir()
            staged = all(
                (unit / stage / stack).is_dir()
                for stage in ("starter", "solution")
                for stack in ("python", "typescript")
            )
            if not (plain or staged):
                missing = [
                    stack for stack in ("python", "typescript") if not (unit / stack).is_dir()
                ]
                errors.append(
                    f"{rel}: SPEC.md unit lacks both stacks "
                    f"(missing {', '.join(missing) or 'starter/solution variants'}; "
                    "need python/+typescript/ or starter+solution variants)"
                )
            if not (unit / "cases.json").is_file():
                errors.append(f"{rel}: SPEC.md unit missing cases.json")
        # Unit parts with no contract: a stray cases.json, or fixture/expected
        # pair, with no SPEC.md is a half-built unit and an error.
        for directory in _iter_dirs(base):
            if (directory / "SPEC.md").is_file():
                continue
            if (directory / "cases.json").is_file():
                errors.append(f"{_rel(directory, root)}: cases.json without SPEC.md")
            elif (directory / "fixtures").is_dir() and (directory / "expected").is_dir():
                errors.append(f"{_rel(directory, root)}: fixtures/+expected/ without SPEC.md")


def check_exercises(errors: list[str], root: Path) -> None:
    base = root / "lectures"
    if not base.is_dir():
        return
    for exercise in sorted(base.glob("lecture-*/exercises/exercise-*")):
        rel = _rel(exercise, root)
        for required_file in ("README.md", "SPEC.md", "verify.sh"):
            if not (exercise / required_file).is_file():
                errors.append(f"{rel}: missing {required_file}")
        for stage in ("starter", "solution"):
            for stack in ("python", "typescript"):
                if not (exercise / stage / stack).is_dir():
                    errors.append(f"{rel}: missing {stage}/{stack}/")
        readme = exercise / "README.md"
        if readme.is_file():
            _check_section_order(readme, EXERCISE_SECTIONS, errors, root)


def check_section_orders(errors: list[str], root: Path) -> None:
    for lecture_readme in sorted(root.glob("lectures/lecture-*/README.md")):
        _check_section_order(lecture_readme, LECTURE_SECTIONS, errors, root)
    for project_readme in sorted(root.glob("projects/project-*/README.md")):
        _check_section_order(project_readme, PROJECT_SECTIONS, errors, root)


def check_orphans(errors: list[str], root: Path) -> None:
    for top in ("lectures", "projects", "skills", "library", "docs", "tools"):
        base = root / top
        if not base.is_dir():
            continue
        for directory in _iter_dirs(base):
            if not any(p.is_file() for p in directory.rglob("*")):
                errors.append(f"{_rel(directory, root)}: orphan directory (no files)")


def counts(root: Path) -> dict[str, int]:
    return {
        "lectures": len(list(root.glob("lectures/lecture-*"))),
        "projects": len(list(root.glob("projects/project-*"))),
        "exercises": len(list(root.glob("lectures/lecture-*/exercises/exercise-*"))),
    }


def check_floors(errors: list[str], root: Path, floors: dict[str, int]) -> None:
    found = counts(root)
    for name, minimum in (
        ("lectures", floors.get("min_lectures", 0)),
        ("projects", floors.get("min_projects", 0)),
        ("exercises", floors.get("min_exercises", 0)),
    ):
        if found[name] < minimum:
            errors.append(
                f"fail-on-empty: found {found[name]} {name} but the manifest requires "
                f"at least {minimum} (broken glob or stale tools/expected_counts.json)"
            )


def check_tree(root: Path, floors: dict[str, int] | None = None) -> list[str]:
    errors: list[str] = []
    check_readmes(errors, root)
    check_units(errors, root)
    check_exercises(errors, root)
    check_section_orders(errors, root)
    check_orphans(errors, root)
    if floors is not None:
        check_floors(errors, root, floors)
    return errors


def main() -> int:
    floors = json.loads(COUNTS_MANIFEST.read_text(encoding="utf-8"))
    errors = check_tree(REPO_ROOT, floors)
    found = counts(REPO_ROOT)
    print(
        f"lint-structure: checked {found['lectures']} lecture(s), "
        f"{found['exercises']} exercise(s), {found['projects']} project(s)"
    )
    for error in errors:
        print(f"  FAIL {error}")
    if errors:
        print(f"lint-structure: {len(errors)} error(s)")
        return 1
    print("lint-structure: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
