"""snr-calculator exercise, Python solution.

Computes per-task instruction signal-to-noise for one tree: relevant
instruction lines (tag-matched) over loaded lines. Contract: ../../SPEC.md.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RULE_RE = re.compile(r"^- \[([a-z]+)(!?)\] (.+)$")


def read_lines(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


def relevant_count(lines: list[str], topics: list[str]) -> int:
    """An instruction line is relevant when its TAG names one of the task's
    topics. Prose that mentions a topic word is context cost, not signal."""
    count = 0
    for line in lines:
        match = RULE_RE.match(line)
        if match and match.group(1) in topics:
            count += 1
    return count


def snr_report(tree: Path, tasks: list[dict]) -> dict:
    lines = read_lines(tree / "AGENTS.md")
    loaded = len(lines)
    rows = []
    snr_total = 0.0
    for task in tasks:
        relevant = relevant_count(lines, task["topics"])
        snr = relevant / loaded if loaded else 0.0
        snr_total += snr
        rows.append({
            "id": task["id"],
            "loaded_lines": loaded,
            "relevant_lines": relevant,
            "snr": snr,
        })
    return {
        "tasks": rows,
        "mean_snr": snr_total / len(rows) if rows else 0.0,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: main.py <tree-dir> <tasks.json>", file=sys.stderr)
        return 2
    tree = Path(argv[1])
    if not (tree / "AGENTS.md").is_file():
        print(f"error: no AGENTS.md in {tree}", file=sys.stderr)
        return 2
    try:
        tasks = json.loads(Path(argv[2]).read_text(encoding="utf-8"))["tasks"]
    except OSError as error:
        print(f"error: cannot read tasks: {error}", file=sys.stderr)
        return 2
    print(json.dumps(snr_report(tree, tasks), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
