"""Summarise the A1 A/B from exports/: R1 and R3 runs failing per arm, ready to paste.

Usage (from the repository root, after the A/B command in SPEC.md has finished):

    uv run python section-1-instructions/assignment/ab_summary.py --batch a1-<name>
        [--exports exports] [--bare NAME] [--harness NAME]

Reads only local files: `exports/experiments/<name>.json` (one per arm, picked by the batch label
in its metadata) and `exports/scores/<run_id>.json` (one ScoreRecord per run). No
API keys, no model calls. Prints Markdown blocks for ab-report.md. A run fails R1 when it has at
least one new R1 violation (the section 1 primary measure) and fails R3 when it has at least one
new R3 failure. Counts, never percentages (a course rule).

Exit 0 when both arms were found, 2 when an arm is missing or ambiguous.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ARMS = ("bare", "harness")
TRACES_PER_RUN = 2  # agent root + referee evaluator


def _experiments(exports: Path, batch: str) -> dict[str, list[dict[str, Any]]]:
    found: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    for path in sorted((exports / "experiments").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("metadata", {}).get("batch") == batch and data.get("arm") in found:
            found[data["arm"]].append(data)
    return found


def _records(exports: Path, experiment: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for run_id in experiment.get("rows", []):
        path = exports / "scores" / f"{run_id}.json"
        if not path.is_file():
            print(f"! {experiment['arm']}: no score export for run {run_id}")
            continue
        records.append(json.loads(path.read_text(encoding="utf-8")))
    return records


def _fails(records: list[dict[str, Any]], field: str) -> str:
    return f"{sum(1 for r in records if int(r.get(field) or 0) >= 1)}/{len(records)}"


def _task(record: dict[str, Any]) -> str:
    return f"{record.get('feature_id')} {record.get('variant')} ({record.get('checkpoint')})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--batch", required=True, help="the --batch label of the A/B command")
    parser.add_argument("--exports", type=Path, default=Path("exports"))
    parser.add_argument("--bare", help="experiment name, when the batch has several bare ones")
    parser.add_argument("--harness", help="experiment name, when the batch has several")
    args = parser.parse_args(argv)

    found = _experiments(args.exports, args.batch)
    chosen: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        wanted = getattr(args, arm)
        options = [e for e in found[arm] if wanted is None or e.get("name") == wanted]
        if not options:
            print(f"x no experiments for arm {arm} with batch {args.batch} in {args.exports}")
            return 2
        if len(options) > 1:
            names = ", ".join(e.get("name", "?") for e in options)
            print(f"x several {arm} experiments for batch {args.batch}: {names}")
            print(f"  pass --{arm} <name> to pick one")
            return 2
        chosen[arm] = options[0]

    records = {arm: _records(args.exports, chosen[arm]) for arm in ARMS}
    bare, harness = records["bare"], records["harness"]
    meta = chosen["harness"].get("metadata", {})
    runs = sorted({len(bare), len(harness)})

    print("## Setup values")
    print()
    print(f"- Runs per arm: {' and '.join(str(n) for n in runs)}")
    print(f"- Model and reasoning effort: {meta.get('model')}, {meta.get('effort')}")
    print()
    print("## Results")
    print()
    print("| Measure | Bare arm (runs failing of N) | Harness arm (runs failing of N) |")
    print("|---|---|---|")
    print(
        "| R1: runs with at least one new R1 violation | "
        f"{_fails(bare, 'r1_new_violations')} | {_fails(harness, 'r1_new_violations')} |"
    )
    print(
        "| R3: runs with at least one new R3 failure | "
        f"{_fails(bare, 'r3_new_failures')} | {_fails(harness, 'r3_new_failures')} |"
    )
    leaks = [sum(int(r.get("r1_leaks") or 0) for r in rs) for rs in (bare, harness)]
    print(f"| R1 leaks (sum over runs) | {leaks[0]} | {leaks[1]} |")
    stopped = [
        sum(1 for r in rs if str(r.get("status", "")).startswith(("ABORTED", "ERROR")))
        for rs in (bare, harness)
    ]
    print(f"| Runs aborted or errored | {stopped[0]} | {stopped[1]} |")
    print()
    print("## Per task (runs failing of runs)")
    print()
    print("| Task | R1 bare | R1 harness | R3 bare | R3 harness |")
    print("|---|---|---|---|---|")
    for task in sorted({_task(r) for r in bare + harness}):
        b = [r for r in bare if _task(r) == task]
        h = [r for r in harness if _task(r) == task]
        print(
            f"| {task} | {_fails(b, 'r1_new_violations')} | {_fails(h, 'r1_new_violations')} | "
            f"{_fails(b, 'r3_new_failures')} | {_fails(h, 'r3_new_failures')} |"
        )
    print()
    print("## Links")
    print()
    print(f"- Bare experiment: {chosen['bare'].get('url') or 'not recorded'}")
    print(f"- Harness experiment: {chosen['harness'].get('url') or 'not recorded'}")
    comparison = chosen["harness"].get("comparison_url") or chosen["bare"].get("comparison_url")
    print(f"- Comparison view: {comparison or 'not recorded'}")
    print()
    cost = sum(
        float(r.get("cost_usd") or 0) + float(r.get("review_cost_usd") or 0) for r in bare + harness
    )
    print("## Cost and traces")
    print()
    print(f"- Cost: ${cost:.6f} (run and review cost in the score exports)")
    planned = TRACES_PER_RUN * (len(bare) + len(harness))
    print(
        f"- Traces: read the count on your LangSmith usage page (planned: {TRACES_PER_RUN} per "
        f"run, {planned} for these runs)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
