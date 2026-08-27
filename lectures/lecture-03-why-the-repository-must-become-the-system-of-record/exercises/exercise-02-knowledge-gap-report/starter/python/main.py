"""knowledge-gap-report exercise, Python starter.

The report plumbing works; the visibility rule does not. in_repo() is a
naive first draft that counts any location MENTIONING "repo" as in-repo,
so a Confluence page about repo guidelines counts as visible to the agent.
Fix in_repo() per SPEC.md. Run ../../verify.sh --stack=python until it
exits 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

GAP_THRESHOLD = 0.1


def in_repo(location: str) -> bool:
    # Naive draft: mentioning a repository is not being in one. Exercise:
    # a decision is visible only when its location is a repository path,
    # marked by the exact prefix "repo:".
    return "repo" in location.lower()


def gap_report(entries: list[dict]) -> dict:
    inside = [entry for entry in entries if in_repo(entry["location"])]
    outside = [entry for entry in entries if not in_repo(entry["location"])]
    total = len(entries)
    gap = len(outside) / total if total else 0.0
    return {
        "total": total,
        "in_repo": len(inside),
        "outside": len(outside),
        "visibility_gap": gap,
        "critical_outside": [entry["id"] for entry in outside if entry["critical"]],
        "verdict": "acceptable" if gap <= GAP_THRESHOLD else "needs-externalization",
    }


def parse_inventory(text: str) -> list[dict]:
    entries = []
    for number, line in enumerate(text.split("\n"), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"malformed inventory at line {number}: {error}") from error
        for field in ("id", "decision", "location", "critical"):
            if field not in entry:
                raise ValueError(f"malformed inventory at line {number}: missing {field!r}")
        entries.append(entry)
    return entries


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: main.py <inventory.jsonl>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        print(f"error: cannot read inventory: {error}", file=sys.stderr)
        return 2
    try:
        entries = parse_inventory(text)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(gap_report(entries), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
