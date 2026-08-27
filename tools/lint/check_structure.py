#!/usr/bin/env python3
"""Structure checker.

Enforces the repository conventions that rot silently if unchecked
(docs/conventions.md is the human-readable statement of the same rules):

1. Every curriculum directory that must carry a README.md has one.
2. Every conformance unit (SPEC.md) is complete: fixtures/, expected/,
   both stacks present (python/typescript or starter+solution variants),
   and cases.json.
3. Every exercise directory is complete: README.md, SPEC.md, verify.sh,
   starter/{python,typescript}, solution/{python,typescript}.
4. Lecture and project READMEs follow the required H2 section order.
5. No orphan directories (empty dirs, or dirs with no files anywhere below).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
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


def _iter_dirs(base: Path):
    for path in sorted(base.rglob("*")):
        if path.is_dir() and not any(part in SKIP_DIRS for part in path.parts):
            yield path


def _headings(md: Path) -> list[str]:
    text = md.read_text(encoding="utf-8")
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return [m.group(1).strip() for m in re.finditer(r"^##\s+(.*)$", text, re.MULTILINE)]


def _check_section_order(md: Path, required: list[str], errors: list[str]) -> None:
    present = _headings(md)
    positions = []
    for section in required:
        matches = [i for i, h in enumerate(present) if h.lower().startswith(section.lower())]
        if not matches:
            errors.append(f"{md.relative_to(REPO_ROOT)}: missing section '## {section}'")
        else:
            positions.append((section, matches[0]))
    ordered = [p for _, p in positions]
    if ordered != sorted(ordered):
        errors.append(f"{md.relative_to(REPO_ROOT)}: sections out of required order")


def check_readmes(errors: list[str]) -> None:
    needs_readme = []
    for top in ("lectures", "projects", "skills", "library", "tools"):
        base = REPO_ROOT / top
        if not base.is_dir():
            continue
        needs_readme.append(base)
        for child in sorted(base.iterdir()):
            if child.is_dir() and child.name not in SKIP_DIRS:
                needs_readme.append(child)
    for directory in needs_readme:
        if not (directory / "README.md").is_file():
            errors.append(f"{directory.relative_to(REPO_ROOT)}: missing README.md")


def check_units(errors: list[str]) -> None:
    for top in ("lectures", "projects"):
        base = REPO_ROOT / top
        if not base.is_dir():
            continue
        for spec in sorted(base.rglob("SPEC.md")):
            unit = spec.parent
            rel = unit.relative_to(REPO_ROOT)
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
                errors.append(
                    f"{rel}: SPEC.md unit lacks both stacks "
                    "(need python/+typescript/ or starter+solution variants)"
                )
            if not (unit / "cases.json").is_file():
                errors.append(f"{rel}: SPEC.md unit missing cases.json")


def check_exercises(errors: list[str]) -> None:
    base = REPO_ROOT / "lectures"
    if not base.is_dir():
        return
    for exercise in sorted(base.glob("lecture-*/exercises/exercise-*")):
        rel = exercise.relative_to(REPO_ROOT)
        for required_file in ("README.md", "SPEC.md", "verify.sh"):
            if not (exercise / required_file).is_file():
                errors.append(f"{rel}: missing {required_file}")
        for stage in ("starter", "solution"):
            for stack in ("python", "typescript"):
                if not (exercise / stage / stack).is_dir():
                    errors.append(f"{rel}: missing {stage}/{stack}/")
        readme = exercise / "README.md"
        if readme.is_file():
            _check_section_order(readme, EXERCISE_SECTIONS, errors)


def check_section_orders(errors: list[str]) -> None:
    for lecture_readme in sorted(REPO_ROOT.glob("lectures/lecture-*/README.md")):
        _check_section_order(lecture_readme, LECTURE_SECTIONS, errors)
    for project_readme in sorted(REPO_ROOT.glob("projects/project-*/README.md")):
        _check_section_order(project_readme, PROJECT_SECTIONS, errors)


def check_orphans(errors: list[str]) -> None:
    for top in ("lectures", "projects", "skills", "library", "docs", "tools"):
        base = REPO_ROOT / top
        if not base.is_dir():
            continue
        for directory in _iter_dirs(base):
            if not any(p.is_file() for p in directory.rglob("*")):
                errors.append(f"{directory.relative_to(REPO_ROOT)}: orphan directory (no files)")


def main() -> int:
    errors: list[str] = []
    check_readmes(errors)
    check_units(errors)
    check_exercises(errors)
    check_section_orders(errors)
    check_orphans(errors)

    lectures = len(list(REPO_ROOT.glob("lectures/lecture-*")))
    projects = len(list(REPO_ROOT.glob("projects/project-*")))
    exercises = len(list(REPO_ROOT.glob("lectures/lecture-*/exercises/exercise-*")))
    print(
        f"lint-structure: checked {lectures} lecture(s), {exercises} exercise(s), "
        f"{projects} project(s)"
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
