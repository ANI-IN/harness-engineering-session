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
    "Acceptance runs",
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
            # Third accepted shape (projects): a complete dual-track
            # solution/ next to a NON-CODE starter/ (e.g. only a task
            # prompt), where the starter is an experimental condition, not a
            # partial implementation. This shape must be DECLARED by the
            # marker line in the unit's SPEC.md; it is never inferred from
            # missing directories, so a project that simply forgot a starter
            # track stays an error. Declaring the marker while shipping code
            # stacks in starter/ is a contradiction and also an error.
            spec_text = spec.read_text(encoding="utf-8")
            declares_non_code_starter = NON_CODE_STARTER_MARKER in spec_text
            starter_has_code = any(
                (unit / "starter" / stack).is_dir() for stack in ("python", "typescript")
            )
            solution_staged = (
                declares_non_code_starter
                and (unit / "starter").is_dir()
                and not starter_has_code
                and (unit / "solution" / "python").is_dir()
                and (unit / "solution" / "typescript").is_dir()
            )
            if declares_non_code_starter and starter_has_code:
                errors.append(
                    f"{rel}: SPEC.md declares '{NON_CODE_STARTER_MARKER}' but starter/ "
                    "contains implementation stack(s); remove the marker or the code"
                )
            if not (plain or staged or solution_staged):
                if (unit / "starter").is_dir() and (unit / "solution").is_dir():
                    missing = [
                        f"{stage}/{stack}"
                        for stage in ("starter", "solution")
                        for stack in ("python", "typescript")
                        if not (unit / stage / stack).is_dir()
                    ]
                    errors.append(
                        f"{rel}: staged SPEC.md unit is missing {', '.join(missing)}; a "
                        "starter without both stacks is only valid when SPEC.md declares "
                        f"'{NON_CODE_STARTER_MARKER}' and starter/ holds no code at all"
                    )
                else:
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


JUSTIFICATION_MARKER = "Starter-divergence justification:"
NON_CODE_STARTER_MARKER = "Starter-shape: non-code"


def _formatting_skeleton(value: str) -> str:
    """Strip everything except alphanumerics; two values with equal skeletons
    differ only in punctuation, markers, or whitespace."""
    return re.sub(r"[^0-9A-Za-z]+", "", value)


def check_starter_divergence(exercise: Path, rel: str, errors: list[str]) -> None:
    """The genuine-partial standard: a starter's first divergence must be a
    value mismatch inside a populated structure, and the mismatch must change
    content. A null-vs-value diff reads as "not implemented" and is rejected
    outright; a string diff whose two sides are equal once formatting
    characters are removed makes the learner debug punctuation, not the
    concept, and is rejected unless justified; a length diff (or a
    missing/unexpected key) is accepted only when the exercise's SPEC.md
    carries a one-line justification starting with the marker. The
    formatting rule deliberately covers strings only: numeric diffs like
    -2 != 2 are sign flips, which are content."""
    divergence_path = exercise / "expected" / "starter-divergence.txt"
    if not divergence_path.is_file():
        return  # missing-file error is reported by the required-files check
    signature = divergence_path.read_text(encoding="utf-8").strip()
    spec_path = exercise / "SPEC.md"
    spec_text = spec_path.read_text(encoding="utf-8") if spec_path.is_file() else ""

    if re.search(r"(^|[ (])None != ", signature) or re.search(r" != None([),]|$)", signature):
        errors.append(
            f"{rel}: starter divergence is null-vs-value ({signature!r}); it reads as "
            "'not implemented' rather than 'wrong', so redesign the starter to produce "
            "a wrong value inside a populated structure"
        )
        return
    quoted_pair = re.search(r": '(.*)' != '(.*)'$", signature)
    if quoted_pair is not None:
        left, right = quoted_pair.group(1), quoted_pair.group(2)
        if left != right and _formatting_skeleton(left) == _formatting_skeleton(right):
            if JUSTIFICATION_MARKER not in spec_text:
                errors.append(
                    f"{rel}: starter divergence is formatting-only ({signature!r}); the two "
                    "values are identical once formatting characters are removed, so the "
                    "learner would debug punctuation, not the exercise's concept. Redesign "
                    "the starter so the divergence changes content, or add a line starting "
                    f"'{JUSTIFICATION_MARKER}' to SPEC.md if formatting IS the concept"
                )
            return
    needs_justification = (
        re.search(r": length \d+ != \d+", signature)
        or "missing in output" in signature
        or "unexpected key" in signature
    )
    if needs_justification and JUSTIFICATION_MARKER not in spec_text:
        errors.append(
            f"{rel}: starter divergence is a structural diff ({signature!r}) with no "
            f"justification; add a line starting '{JUSTIFICATION_MARKER}' to SPEC.md "
            "explaining why this is the right signal, or redesign the starter so the "
            "divergence is a value mismatch"
        )


def check_exercises(errors: list[str], root: Path) -> None:
    base = root / "lectures"
    if not base.is_dir():
        return
    for exercise in sorted(base.glob("lecture-*/exercises/exercise-*")):
        rel = _rel(exercise, root)
        required_files = (
            "README.md", "SPEC.md", "verify.sh", "expected/starter-divergence.txt",
        )
        for required_file in required_files:
            if not (exercise / required_file).is_file():
                errors.append(f"{rel}: missing {required_file}")
        check_starter_divergence(exercise, rel, errors)
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
