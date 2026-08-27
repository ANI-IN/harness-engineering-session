"""instruction-stats: measure what an instruction architecture costs.

For each instruction tree (an AGENTS.md entry file plus optional docs/
topic files), simulate the loading rule (entry always; docs/<topic>.md for
each task topic when present), compute per-task signal-to-noise, and locate
hard constraints by zone, flagging the ones buried in the middle of long
files. SPEC.md pins the formats; expected/ is the grading authority.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RULE_RE = re.compile(r"^- \[([a-z]+)(!?)\] (.+)$")
BURIED_MIN_LINES = 20
ZONES = ("top", "middle", "bottom")


def parse_file(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    rules = []
    for number, line in enumerate(lines, 1):
        match = RULE_RE.match(line)
        if match:
            rules.append({
                "topic": match.group(1),
                "hard": match.group(2) == "!",
                "text": match.group(3),
                "line": number,
            })
    return {"lines": len(lines), "rules": rules}


def zone_of(line: int, total: int) -> str:
    return ZONES[min((line - 1) * 3 // total, 2)] if total else "top"


def analyze_tree(tree: Path, tasks: list[dict]) -> dict:
    entry = parse_file(tree / "AGENTS.md")
    docs = {}
    docs_dir = tree / "docs"
    if docs_dir.is_dir():
        for doc in sorted(docs_dir.glob("*.md")):
            docs[doc.stem] = parse_file(doc)

    task_rows = []
    for task in tasks:
        loaded = [("AGENTS.md", entry)]
        for topic in task["topics"]:
            if topic in docs:
                loaded.append((f"docs/{topic}.md", docs[topic]))
        loaded_lines = sum(info["lines"] for _, info in loaded)
        relevant = sum(
            1
            for _, info in loaded
            for rule in info["rules"]
            if rule["topic"] in task["topics"]
        )
        task_rows.append({
            "id": task["id"],
            "loaded_lines": loaded_lines,
            "relevant_lines": relevant,
            "snr": relevant / loaded_lines if loaded_lines else 0.0,
        })

    hard_constraints = []
    for name, info in [("AGENTS.md", entry)] + [
        (f"docs/{stem}.md", docs[stem]) for stem in sorted(docs)
    ]:
        for rule in info["rules"]:
            if rule["hard"]:
                zone = zone_of(rule["line"], info["lines"])
                hard_constraints.append({
                    "text": rule["text"],
                    "file": name,
                    "line": rule["line"],
                    "zone": zone,
                    "buried": zone == "middle" and info["lines"] > BURIED_MIN_LINES,
                })

    # Plain left-to-right accumulation, per SPEC: Python's built-in sum()
    # uses Neumaier-compensated summation for floats (3.12+), which is one
    # ulp more accurate than JavaScript's naive reduce and breaks parity.
    snr_total = 0.0
    for row in task_rows:
        snr_total += row["snr"]

    total_lines = entry["lines"] + sum(info["lines"] for info in docs.values())
    return {
        "name": tree.name,
        "files": 1 + len(docs),
        "total_lines": total_lines,
        "entry_lines": entry["lines"],
        "tasks": task_rows,
        "mean_snr": snr_total / len(task_rows) if task_rows else 0.0,
        "hard_constraints": hard_constraints,
        "buried_hard_constraints": sum(1 for h in hard_constraints if h["buried"]),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: main.py <trees-dir> <tasks.json>", file=sys.stderr)
        return 2
    trees_dir = Path(argv[1])
    tasks_path = Path(argv[2])
    if not trees_dir.is_dir():
        print(f"error: not a directory: {trees_dir}", file=sys.stderr)
        return 2
    try:
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))["tasks"]
    except OSError as error:
        print(f"error: cannot read tasks: {error}", file=sys.stderr)
        return 2

    trees = [analyze_tree(tree, tasks) for tree in sorted(trees_dir.iterdir()) if tree.is_dir()]
    report = {
        "trees": trees,
        "comparison": {
            "mean_snr": {tree["name"]: tree["mean_snr"] for tree in trees},
            "buried_hard_constraints": {
                tree["name"]: tree["buried_hard_constraints"] for tree in trees
            },
        },
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
