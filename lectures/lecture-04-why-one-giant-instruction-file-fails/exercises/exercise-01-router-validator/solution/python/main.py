"""router-validator exercise, Python solution.

Validates a router-style instruction tree against four structural checks:
short entry, resolvable routes, hard constraints only in the entry, and no
rule text duplicated across files. Contract: ../../SPEC.md.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ENTRY_MAX_LINES = 20
RULE_RE = re.compile(r"^- \[([a-z]+)(!?)\] (.+)$")
ROUTE_RE = re.compile(r"^- (docs/[a-z-]+\.md)\b")


def read_lines(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


def tree_files(tree: Path) -> list[tuple[str, list[str]]]:
    files = [("AGENTS.md", read_lines(tree / "AGENTS.md"))]
    docs_dir = tree / "docs"
    if docs_dir.is_dir():
        for doc in sorted(docs_dir.glob("*.md")):
            files.append((f"docs/{doc.name}", read_lines(doc)))
    return files


def check_entry_length(tree: Path) -> list[dict]:
    lines = read_lines(tree / "AGENTS.md")
    if len(lines) > ENTRY_MAX_LINES:
        return [{
            "file": "AGENTS.md", "line": len(lines),
            "detail": f"entry file is {len(lines)} lines; the router limit is {ENTRY_MAX_LINES}",
        }]
    return []


def check_routes_resolve(tree: Path) -> list[dict]:
    violations = []
    for number, line in enumerate(read_lines(tree / "AGENTS.md"), 1):
        match = ROUTE_RE.match(line)
        if match and not (tree / match.group(1)).is_file():
            violations.append({
                "file": "AGENTS.md", "line": number,
                "detail": f"route target does not exist: {match.group(1)}",
            })
    return violations


def check_hard_in_entry(tree: Path) -> list[dict]:
    violations = []
    for name, lines in tree_files(tree):
        if name == "AGENTS.md":
            continue
        for number, line in enumerate(lines, 1):
            match = RULE_RE.match(line)
            if match and match.group(2) == "!":
                violations.append({
                    "file": name, "line": number,
                    "detail": f"hard constraint outside the entry file: {match.group(3)}",
                })
    return violations


def check_no_duplicates(tree: Path) -> list[dict]:
    seen: dict[str, str] = {}
    violations = []
    for name, lines in tree_files(tree):
        for number, line in enumerate(lines, 1):
            match = RULE_RE.match(line)
            if not match:
                continue
            text = match.group(3)
            if text in seen:
                violations.append({
                    "file": name, "line": number,
                    "detail": f"rule text duplicated (also in {seen[text]}): {text}",
                })
            else:
                seen[text] = name
    return violations


CHECKS = [
    ("entry-length", check_entry_length),
    ("routes-resolve", check_routes_resolve),
    ("hard-in-entry", check_hard_in_entry),
    ("no-duplicates", check_no_duplicates),
]


def validate(tree: Path) -> dict:
    checks = []
    for check_id, run in CHECKS:
        violations = run(tree)
        checks.append({"id": check_id, "passed": not violations, "violations": violations})
    return {"checks": checks, "ok": all(check["passed"] for check in checks)}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: main.py <tree-dir>", file=sys.stderr)
        return 2
    tree = Path(argv[1])
    if not (tree / "AGENTS.md").is_file():
        print(f"error: no AGENTS.md in {tree}", file=sys.stderr)
        return 2
    print(json.dumps(validate(tree), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
