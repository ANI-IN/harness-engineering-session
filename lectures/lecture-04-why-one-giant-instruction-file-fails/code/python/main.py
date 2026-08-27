"""instruction-walk: demonstrate what an instruction architecture costs.

`walk` is the demo: a budgeted deterministic reader works one task against
one instruction tree, reading files top-down until the line budget runs
out, following only the routes it has actually read. The failure is
behavioral: with a realistic budget the monolith's buried hard constraint
is never read (exit 1) while the router's is (exit 0). `stats` is the
supporting evidence: per-task signal-to-noise and constraint zones for
every tree. SPEC.md pins both; expected/ is the grading authority.
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


def walk_tree(tree: Path, task: dict, budget: int) -> dict:
    """The budgeted deterministic reader (SPEC.md, "The reader"). Files are
    read whole-file top-down until the budget runs out; a route is followed
    only if the line naming it was actually read."""
    entry = parse_file(tree / "AGENTS.md")
    remaining = budget
    visited = []

    def read_file(name: str, info: dict) -> int:
        nonlocal remaining
        lines_read = min(remaining, info["lines"])
        remaining -= lines_read
        visited.append({"file": name, "lines_read": lines_read, "lines_total": info["lines"]})
        return lines_read

    entry_read = read_file("AGENTS.md", entry)
    entry_lines = (tree / "AGENTS.md").read_text(encoding="utf-8").split("\n")[:entry_read]
    for topic in task["topics"]:
        doc_path = tree / "docs" / f"{topic}.md"
        route_seen = any(f"docs/{topic}.md" in line for line in entry_lines)
        if doc_path.is_file() and route_seen and remaining > 0:
            read_file(f"docs/{topic}.md", parse_file(doc_path))

    read_of = {item["file"]: item["lines_read"] for item in visited}
    files = [("AGENTS.md", entry)]
    docs_dir = tree / "docs"
    if docs_dir.is_dir():
        files += [(f"docs/{doc.stem}.md", parse_file(doc)) for doc in sorted(docs_dir.glob("*.md"))]
    constraints = []
    for name, info in files:
        for rule in info["rules"]:
            if rule["hard"]:
                constraints.append({
                    "text": rule["text"],
                    "file": name,
                    "line": rule["line"],
                    "read": rule["line"] <= read_of.get(name, 0),
                })
    missed = sum(1 for constraint in constraints if not constraint["read"])
    return {
        "tree": tree.name,
        "task": task["id"],
        "budget": budget,
        "files_visited": visited,
        "lines_spent": budget - remaining,
        "hard_constraints": constraints,
        "missed": missed,
    }


def load_tasks(tasks_path: Path) -> list[dict] | None:
    try:
        return json.loads(tasks_path.read_text(encoding="utf-8"))["tasks"]
    except OSError:
        return None


USAGE = (
    "usage: main.py walk <tree-dir> <tasks.json> <task-id> --budget N | "
    "main.py stats <trees-dir> <tasks.json>"
)


def run_stats(argv: list[str]) -> int:
    if len(argv) != 2:
        print(USAGE, file=sys.stderr)
        return 2
    trees_dir = Path(argv[0])
    if not trees_dir.is_dir():
        print(f"error: not a directory: {trees_dir}", file=sys.stderr)
        return 2
    tasks = load_tasks(Path(argv[1]))
    if tasks is None:
        print(f"error: cannot read tasks: {argv[1]}", file=sys.stderr)
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


def run_walk(argv: list[str]) -> int:
    if len(argv) != 5 or argv[3] != "--budget" or not argv[4].isdigit():
        print(USAGE, file=sys.stderr)
        return 2
    tree = Path(argv[0])
    if not (tree / "AGENTS.md").is_file():
        print(f"error: not an instruction tree: {tree}", file=sys.stderr)
        return 2
    tasks = load_tasks(Path(argv[1]))
    if tasks is None:
        print(f"error: cannot read tasks: {argv[1]}", file=sys.stderr)
        return 2
    task = next((entry for entry in tasks if entry["id"] == argv[2]), None)
    if task is None:
        print(f"error: no task with id {argv[2]}", file=sys.stderr)
        return 2
    report = walk_tree(tree, task, int(argv[4]))
    print(json.dumps(report, indent=2))
    return 1 if report["missed"] else 0


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "stats":
        return run_stats(argv[2:])
    if len(argv) >= 2 and argv[1] == "walk":
        return run_walk(argv[2:])
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
