"""Summarise a `shipharness testgen` report as a Markdown table plus the discard reasons.

    python scripts/summarize_report.py <out-dir>/testgen-report.json

Prints the table for the evidence report's Results section. Deterministic; reads one file.
Prints `ERROR <reason>` on one line and exits 1 when the report cannot be read.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def summarize(report: dict[str, Any]) -> list[str]:
    results = report.get("results", [])
    proposed = list(dict.fromkeys(str(r["test_id"]) for r in results))
    failed = [r for r in results if not r.get("passed")]
    per_filter: dict[int, int] = {}
    for r in failed:
        per_filter[int(r["filter"])] = per_filter.get(int(r["filter"]), 0) + 1
    lines = [
        "| Measure | Value |",
        "|---|---|",
        f"| Run id | {report.get('run_id', '')} |",
        f"| Status | {report.get('status', '')} |",
        f"| Proposed tests (evaluated) | {len(proposed)} |",
        f"| Kept by testgen (filters 1-5) | {len(report.get('kept', []))} |",
        f"| Not evaluated (over --max-tests) | {len(report.get('not_evaluated', []))} |",
    ]
    if isinstance(report.get("filter6"), dict):  # written by apply_filter --update-report
        lines.append(f"| Kept after filter 6 | {len(report['filter6'].get('kept', []))} |")
    lines += [f"| Discarded by filter {n} | {per_filter[n]} |" for n in sorted(per_filter)]
    lines += ["", "Discarded tests:"]
    lines += [f"- {r['test_id']}: filter {r['filter']}: {r.get('reason', '')}" for r in failed]
    return lines


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("ERROR usage: summarize_report.py <testgen-report.json>")
        return 1
    try:
        report = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ERROR cannot read {args[0]}: {exc}")
        return 1
    print("\n".join(summarize(report)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
