#!/usr/bin/env python3
"""Scaffold a house rule: a rule doc, a check stub, and a test stub that fails until it is written.

Usage:
    python new_rule.py --id Example --title "Soft-deleted rows never appear" [--root .]
        [--slug soft-delete] [--docs-dir docs/rules] [--checks-dir checks] [--tests-dir tests]
        [--force] [--dry-run]

Writes, relative to --root:
    <docs-dir>/<ID>-<slug>.md                 from ../assets/rule-template.md
    <checks-dir>/check_<id>_<slug>.py         prints `ERROR <ID> <path>:<line>: ... Fix: ...`
    <tests-dir>/test_check_<id>_<slug>.py     one failing test (write the seeded violation) and
                                              one clean-code test
Refuses to overwrite existing files unless --force. Standard library only (Python 3.10+).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "rule-template.md"
RULE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,15}$")

CHECK_STUB = '''"""Check for {rule_id}: {title}.

Rule doc: {doc_path}
Run: python {check_path} [repo]
Prints one ERROR line per new violation with the fix on the same line, then a summary line.
Exit 0 when there are no new violations, 1 otherwise.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

RULE_ID = "{rule_id}"
REMEDIATION = "<what to do instead, and which doc to read>"
# "path:line" entries that existed when the rule was adopted; new code must follow the rule.
BASELINE: set[str] = set()


@dataclass(frozen=True)
class Violation:
    path: str  # relative to the repository root, forward slashes
    line: int
    detail: str  # what is wrong, in one short sentence


def check(repo: Path) -> list[Violation]:
    """Every violation of {rule_id} in `repo`. Replace this body with the real check.

    Typical shapes: walk files and match a pattern; parse Python with `ast` and inspect imports or
    calls; load the app and probe its endpoints.
    """
    violations: list[Violation] = []
    return violations


def main(argv: list[str]) -> int:
    repo = Path(argv[1]) if len(argv) > 1 else Path(".")
    found = [v for v in check(repo) if f"{{v.path}}:{{v.line}}" not in BASELINE]
    for v in found:
        print(f"ERROR {{RULE_ID}} {{v.path}}:{{v.line}}: {{v.detail}}. Fix: {{REMEDIATION}}")
    print(f"{{RULE_ID}}: {{len(found)}} new violations")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
'''

TEST_STUB = '''"""Tests for the {rule_id} check ({title})."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

CHECK_FILE = Path(__file__).resolve().parent / "{relative_check}"


def load_check():
    spec = importlib.util.spec_from_file_location("check_{module_id}", CHECK_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses need the module registered
    spec.loader.exec_module(module)
    return module


def test_catches_a_seeded_violation(tmp_path: Path) -> None:
    # Write the smallest file that breaks {rule_id} into tmp_path, then assert check() reports it.
    # It fails on purpose until you do: a check that never caught anything proves nothing.
    pytest.fail("write a seeded violation of {rule_id} and assert the check finds it")


def test_clean_code_passes(tmp_path: Path) -> None:
    assert load_check().check(tmp_path) == []
'''


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60].rstrip("-") or "rule"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--id", required=True, dest="rule_id", help="rule id, for example Example")
    parser.add_argument("--title", required=True, help="the rule in a few words")
    parser.add_argument("--root", type=Path, default=Path("."), help="repository root")
    parser.add_argument("--slug", help="file name part (default: from the title)")
    parser.add_argument("--docs-dir", default="docs/rules")
    parser.add_argument("--checks-dir", default="checks")
    parser.add_argument("--tests-dir", default="tests")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    args = parser.parse_args(argv)
    if not RULE_ID.match(args.rule_id):
        parser.error("--id must be a letter followed by up to 15 letters or digits, e.g. Example")
    if not args.title.strip():
        parser.error("--title must not be empty")
    args.slug = slugify(args.slug or args.title)
    return args


def plan(args: argparse.Namespace) -> dict[str, str]:
    """Relative path -> file contents."""
    rule_id = args.rule_id
    module_id = f"{rule_id.lower()}_{args.slug.replace('-', '_')}"
    doc_path = f"{args.docs_dir.strip('/')}/{rule_id}-{args.slug}.md"
    check_path = f"{args.checks_dir.strip('/')}/check_{module_id}.py"
    test_path = f"{args.tests_dir.strip('/')}/test_check_{module_id}.py"
    relative_check = Path(os.path.relpath(Path(check_path), Path(test_path).parent)).as_posix()
    title = args.title.strip()
    doc = (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("{{RULE_ID}}", rule_id)
        .replace("{{TITLE}}", title)
        .replace("{{CHECK_PATH}}", check_path)
        .replace("{{TEST_PATH}}", test_path)
    )
    safe_title = title.replace('"', "'").replace("\\", "/")
    values = {
        "rule_id": rule_id,
        "title": safe_title,
        "doc_path": doc_path,
        "check_path": check_path,
        "relative_check": relative_check,
        "module_id": module_id,
    }
    return {
        doc_path: doc,
        check_path: CHECK_STUB.format(**values),
        test_path: TEST_STUB.format(**values),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    files = plan(args)
    root = args.root
    existing = [rel for rel in files if (root / rel).exists()]
    if existing and not args.force:
        for rel in existing:
            print(f"ERROR {rel} exists: pass --force to overwrite")
        return 1
    for rel, text in files.items():
        if args.dry_run:
            print(f"would write {rel}")
            continue
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {rel}")
    if not args.dry_run:
        print(
            "next: fill in the rule doc, make the seeded-violation test fail for the right reason,"
            " then write check() until it passes"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
